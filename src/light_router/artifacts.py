"""Run artifacts: the controllable, inspectable output of a staircase run.

Every staircase run can write a self-contained run directory
``runs/<scenario>/<timestamp>-<gitsha>/`` containing a manifest (config, code
version, data provenance), the routes (GPX + GeoJSON), metrics.csv, a wind
snapshot for re-rendering, and plots. Opt-in via ``--artifacts`` — plain runs
write nothing. See specs/goal-1-baseline.md section 7.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

import numpy as np
import xarray as xr

from .dataset import dataset_extent
from .isochrone import Route, RouterConfig
from .staircase import StaircaseResult, write_csv

MANIFEST_NAME = "manifest.json"
METRICS_NAME = "metrics.csv"
WIND_SNAPSHOT_NAME = "wind_snapshot.npz"


def _package_version() -> str:
    try:
        return pkg_version("light-router")
    except PackageNotFoundError:  # running from a source tree
        return "0.1.0"


def git_sha() -> str:
    """Short commit hash of the working tree, or "unknown" outside git."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def grid_checksum(weather: xr.Dataset) -> str:
    """SHA-256 over the dataset axes and data — the provenance fingerprint."""
    h = hashlib.sha256()
    for name in ("time", "latitude", "longitude"):
        h.update(np.ascontiguousarray(weather[name].values, dtype=float).tobytes())
    for name in sorted(str(v) for v in weather.data_vars):
        h.update(name.encode())
        h.update(np.ascontiguousarray(weather[name].values).tobytes())
    return h.hexdigest()


def new_run_dir(base: Path, scenario: str, sha: str | None = None) -> Path:
    """Create and return ``<base>/<scenario>/<timestamp>-<sha>/``."""
    sha = sha if sha is not None else git_sha()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = base / scenario / f"{timestamp}-{sha}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_manifest(
    run_dir: Path,
    *,
    scenario: str,
    start: tuple[float, float],
    finish: tuple[float, float],
    router_config: RouterConfig,
    staircase: list[int | None],
    weather: xr.Dataset,
    source: dict[str, object],
    code_version: str | None = None,
) -> Path:
    """Write manifest.json: config, code version, data provenance."""
    manifest = {
        "schema_version": 1,
        "scenario": scenario,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_version": code_version if code_version is not None else git_sha(),
        "light_router_version": _package_version(),
        "source": source,
        "data_checksum": grid_checksum(weather),
        "grid": {
            "n_steps": int(weather.sizes["time"]),
            "n_lat": int(weather.sizes["latitude"]),
            "n_lon": int(weather.sizes["longitude"]),
            "variables": sorted(str(v) for v in weather.data_vars),
            "extent_east_west_south_north": list(dataset_extent(weather)),
        },
        "route": {"start": list(start), "finish": list(finish)},
        "router_config": {
            "dt_hours": router_config.dt_hours,
            "n_headings": router_config.n_headings,
            "bin_deg": router_config.bin_deg,
            "max_points": router_config.max_points,
            "finish_radius_nm": router_config.finish_radius_nm,
            "max_hours": router_config.max_hours,
        },
        "staircase": staircase,
    }
    path = run_dir / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def write_wind_snapshot(run_dir: Path, weather: xr.Dataset) -> Path:
    """Write the t=0 wind field, so plots can be re-rendered without the grid."""
    path = run_dir / WIND_SNAPSHOT_NAME
    fields = {
        "lats": weather["latitude"].values,
        "lons": weather["longitude"].values,
        **{
            name: weather[name].isel(time=0).values
            for name in ("u10", "v10")
            if name in weather
        },
    }
    np.savez(path, **fields)  # type: ignore[arg-type]  # numpy stub limitation
    return path


def budget_slug(budget: str) -> str:
    """File-name-safe form of a budget label ("100 KB" -> "100KB")."""
    return budget.replace(" ", "")


def write_artifacts(
    run_dir: Path,
    result: StaircaseResult,
    weather: xr.Dataset,
    *,
    scenario: str,
    start: tuple[float, float],
    finish: tuple[float, float],
    router_config: RouterConfig,
    staircase: list[int | None],
    source: dict[str, object],
    routes: dict[str, Route] | None = None,
    plots: bool = True,
) -> None:
    """Write the full run directory: manifest, metrics, routes, snapshot, plots.

    ``routes`` maps a label to a route to export in addition to the staircase
    rows (e.g. the reference route under "reference").
    """
    from .export import write_route_files
    from .plots import write_plots

    write_manifest(
        run_dir,
        scenario=scenario,
        start=start,
        finish=finish,
        router_config=router_config,
        staircase=staircase,
        weather=weather,
        source=source,
    )
    write_csv(result.rows, run_dir / METRICS_NAME)
    write_wind_snapshot(run_dir, weather)

    write_route_files(run_dir, result.reference, "route_reference")
    for row in result.rows:
        write_route_files(run_dir, row.route, f"route_{budget_slug(row.budget)}")
    for label, route in (routes or {}).items():
        write_route_files(run_dir, route, label)

    if plots:
        write_plots(run_dir, result, weather)
