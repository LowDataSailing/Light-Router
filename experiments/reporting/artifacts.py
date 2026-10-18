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
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

import numpy as np
import xarray as xr

from light_router.dataset import dataset_extent, grid_from_dataset
from experiments.harness.staircase import StaircaseResult, budget_label, write_csv
from experiments.models.passage import PassageResult
from light_router.models.route import Route
from light_router.models.vessel import PolarTable
from light_router.provenance import git_sha

MANIFEST_NAME = "manifest.json"
METRICS_NAME = "metrics.csv"
PASSAGE_NAME = "passage.csv"
CYCLES_NAME = "cycles.csv"
WIND_SNAPSHOT_NAME = "wind_snapshot.npz"


def _package_version() -> str:
    try:
        return pkg_version("light-router")
    except PackageNotFoundError:  # running from a source tree
        return "0.1.0"


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
    router_config: dict[str, float | int | None],
    staircase: list[int | None],
    weather: xr.Dataset,
    source: dict[str, object],
    code_version: str | None = None,
    router: str | None = None,
    polar: PolarTable | None = None,
    polar_source: str | None = None,
) -> Path:
    """Write manifest.json: config, code version, data provenance.

    ``router`` (algorithm name) and ``polar`` (source +
    checksum) record *what* defined the routing model, next to
    the parameters and data provenance — an oracle swap or a polar change
    must be visible in the artifact.
    """
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
        "router_config": router_config,
        "staircase": staircase,
    }
    if router is not None:
        manifest["router"] = {"algorithm": router}
    if polar is not None:
        manifest["polar"] = {
            "source": polar_source if polar_source is not None else "unspecified",
            "checksum": polar.checksum,
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
    router_config: dict[str, float | int | None],
    staircase: list[int | None],
    source: dict[str, object],
    routes: dict[str, Route] | None = None,
    plots: bool = True,
    router: str | None = None,
    polar: PolarTable | None = None,
    polar_source: str | None = None,
) -> None:
    """Write the full run directory: manifest, metrics, routes, snapshot, plots.

    ``routes`` maps a label to a route to export in addition to the staircase
    rows (e.g. the reference route under "reference").
    """
    from experiments.reporting.export import write_route_files
    from experiments.reporting.plots import write_plots

    grid = grid_from_dataset(weather)

    write_manifest(
        run_dir,
        scenario=scenario,
        start=start,
        finish=finish,
        router_config=router_config,
        staircase=staircase,
        weather=weather,
        source=source,
        router=router,
        polar=polar,
        polar_source=polar_source,
    )
    write_csv(result.rows, run_dir / METRICS_NAME)
    write_wind_snapshot(run_dir, weather)

    write_route_files(run_dir, result.reference, "route_reference", grid)
    for row in result.rows:
        write_route_files(run_dir, row.route, f"route_{budget_slug(row.budget)}", grid)
    for label, route in (routes or {}).items():
        write_route_files(run_dir, route, label, grid)

    if plots:
        write_plots(run_dir, result, weather)


def _write_passage_csv(
    path: Path, results: list[PassageResult], price_per_kb: float | None = None
) -> None:
    """One row per budget: the actual passage outcome on measured weather.

    Experienced-weather columns make the safety review possible:
    a budget must buy ETA in time/VMG, never in weather. ``cost_eur``
    prices the delivered bytes at ``price_per_kb`` (Decision
    #21: delivered package bytes only); empty when no price is configured.
    """
    lines = [
        "budget,total_package_bytes,cost_eur,cycles,passage_hours,distance_nm,"
        "max_tws_kt,mean_tws_kt,pct_upwind,pct_downwind,"
        "compute_total_s,compute_mean_s,reached"
    ]
    for result in results:
        cost = (
            f"{result.total_package_bytes / 1000 * price_per_kb:.2f}"
            if price_per_kb is not None
            else ""
        )
        lines.append(
            f"{budget_label(result.budget_bytes)},"
            f"{result.total_package_bytes},{cost},{len(result.cycles)},"
            f"{result.passage_hours:.2f},{result.distance_nm:.1f},"
            f"{result.max_tws_kt:.1f},{result.mean_tws_kt:.1f},"
            f"{100 * result.upwind_fraction:.0f},{100 * result.downwind_fraction:.0f},"
            f"{result.compute_seconds_total:.2f},{result.compute_seconds_mean:.2f},"
            f"{result.reached}"
        )
    path.write_text("\n".join(lines) + "\n")


def _write_cycles_csv(path: Path, results: list[PassageResult]) -> None:
    """One row per planning cycle: what the router received, decided and
    believed. Empty cell = not applicable
    (no data cycle, first plan, unreached, ...). ``compute_s`` is the one
    non-deterministic column — exclude it from artifact-equality checks
    (Decision #18)."""
    lines = [
        "budget,hour,spatial_stride,temporal_stride,bits,"
        "package_bytes,cumulative_bytes,plan_reached,planned_arrival_hour,"
        "planned_bearing_deg,plan_checksum,churn_nm,execution_error_nm,"
        "belief_error_h,forecast_error_kt,forecast_staleness_h,compute_s"
    ]
    for result in results:
        label = budget_label(result.budget_bytes)
        for record in result.cycles:
            config = record.config
            arrival = (
                f"{record.planned_arrival_hour:.1f}"
                if record.planned_arrival_hour is not None
                else ""
            )
            bearing = (
                f"{record.planned_bearing_deg:.1f}"
                if record.planned_bearing_deg is not None
                else ""
            )
            churn = f"{record.churn_nm:.1f}" if record.churn_nm is not None else ""
            execution = (
                f"{record.execution_error_nm:.1f}"
                if record.execution_error_nm is not None
                else ""
            )
            belief = (
                f"{record.belief_error_h:.1f}"
                if record.belief_error_h is not None
                else ""
            )
            fc_error = (
                f"{record.forecast_error_kt:.2f}"
                if record.forecast_error_kt is not None
                else ""
            )
            staleness = (
                f"{record.forecast_staleness_h:.1f}"
                if record.forecast_staleness_h is not None
                else ""
            )
            compute = (
                f"{record.compute_seconds:.3f}"
                if record.compute_seconds is not None
                else ""
            )
            lines.append(
                f"{label},{record.hour:.1f},"
                f"{config.spatial_stride if config else ''},"
                f"{config.temporal_stride if config else ''},"
                f"{config.bits if config else ''},"
                f"{record.package_bytes},{record.cumulative_bytes},"
                f"{record.plan_reached},{arrival},"
                f"{bearing},{record.plan_checksum or ''},{churn},{execution},"
                f"{belief},{fc_error},{staleness},{compute}"
            )
    path.write_text("\n".join(lines) + "\n")


def write_operational_artifacts(
    run_dir: Path,
    results: list[PassageResult],
    truth: xr.Dataset,
    *,
    scenario: str,
    start: tuple[float, float],
    finish: tuple[float, float],
    router_config: dict[str, float | int | None],
    budgets: list[int | None],
    source: dict[str, object],
    plots: bool = True,
    router: str | None = None,
    polar: PolarTable | None = None,
    polar_source: str | None = None,
    price_per_kb: float | None = None,
) -> None:
    """Write the operational run directory: manifest, CSVs, tracks, plots.

    ``truth`` is the measured-weather grid the boat actually sailed on; it
    feeds the manifest provenance checksum, the wind snapshot and the plot
    underlay. ``router``/``polar`` record the routing-model identity;
    ``price_per_kb`` prices the bandwidth ledger.
    """
    from experiments.reporting.export import write_route_files
    from experiments.reporting.plots import write_operational_plots

    truth_grid = grid_from_dataset(truth)

    write_manifest(
        run_dir,
        scenario=scenario,
        start=start,
        finish=finish,
        router_config=router_config,
        staircase=budgets,
        weather=truth,
        source=source,
        router=router,
        polar=polar,
        polar_source=polar_source,
    )
    write_wind_snapshot(run_dir, truth)
    _write_passage_csv(run_dir / PASSAGE_NAME, results, price_per_kb)
    _write_cycles_csv(run_dir / CYCLES_NAME, results)
    for result in results:
        label = budget_label(result.budget_bytes)
        write_route_files(
            run_dir, result.as_route(), f"track_{budget_slug(label)}", truth_grid
        )
    if plots:
        write_operational_plots(run_dir, results, truth)
