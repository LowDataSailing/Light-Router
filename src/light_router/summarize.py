"""Re-render comparisons from an existing run directory.

``python -m light_router.summarize <run_dir>`` reads manifest.json, metrics.csv
and the exported GPX routes, re-renders the plots and prints the summary
table — without re-running the router. Same inputs produce the same artifact
content.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr

from .artifacts import MANIFEST_NAME, METRICS_NAME, WIND_SNAPSHOT_NAME
from .export import read_routes
from .isochrone import Route
from .plots import plot_degradation, plot_size_fidelity, plot_tracks
from .staircase import StaircaseRow
from .metrics import RouteMetrics


def _empty_route() -> Route:
    """Placeholder route for rows rebuilt from CSV (tracks come from GPX)."""
    return Route(
        lat=np.empty(0),
        lon=np.empty(0),
        time=np.empty(0),
        heading=np.empty(0),
        speed=np.empty(0),
        tws=np.empty(0),
        twa=np.empty(0),
        reached=False,
        eta_hours=0.0,
        distance_nm=0.0,
    )


def _rows_from_csv(run_dir: Path) -> list[StaircaseRow]:
    """Rebuild staircase rows (metrics only) from metrics.csv."""
    rows: list[StaircaseRow] = []
    with open(run_dir / METRICS_NAME, newline="") as fh:
        for rec in csv.DictReader(fh):
            metrics = RouteMetrics(
                reached=rec["reached"] == "True",
                eta_diff_pct=float(rec["eta_diff_pct"]),
                distance_diff_pct=float(rec["distance_diff_pct"]),
                vmg_diff_kt=float(rec["vmg_diff_kt"]),
                max_wind_diff_kt=float(rec["max_wind_diff_kt"]),
                decision_divergence=rec["decision_divergence"] == "True",
                initial_bearing_diff_deg=float(rec["initial_bearing_diff_deg"]),
                geographic_divergence_nm=float(rec["geographic_divergence_nm"]),
            )
            label = rec["budget"]
            raw_bytes = rec.get("budget_bytes", "")
            if raw_bytes:
                budget_bytes: int | None = int(raw_bytes)
            elif label == "unlimited":
                budget_bytes = None
            else:  # CSV written before the budget_bytes column existed
                budget_bytes = _budget_bytes(label)
            rows.append(
                StaircaseRow(
                    budget=label,
                    budget_bytes=budget_bytes,
                    package_bytes=int(rec["package_bytes"]),
                    spatial_stride=int(rec["spatial_stride"]),
                    temporal_stride=int(rec["temporal_stride"]),
                    bits=int(rec["bits"]),
                    metrics=metrics,
                    route=_empty_route(),
                )
            )
    return rows


def _budget_bytes(label: str) -> int:
    """Parse a budget label like "100 KB" back into bytes."""
    value, unit = label.split()
    return int(float(value)) * {"B": 1, "KB": 1000, "MB": 1_000_000}[unit]


def _routes_from_gpx(run_dir: Path) -> dict[str, Route]:
    """Rebuild plottable routes from the exported GPX files."""
    tracks = read_routes(run_dir)
    routes: dict[str, Route] = {}
    for name, points in tracks.items():
        if not points:
            continue
        lats, lons = zip(*points)
        n = len(lats)
        routes[name.removeprefix("route_")] = Route(
            lat=np.asarray(lats),
            lon=np.asarray(lons),
            time=np.arange(n, dtype=float),
            heading=np.zeros(n),
            speed=np.zeros(n),
            tws=np.zeros(n),
            twa=np.zeros(n),
            reached=True,
            eta_hours=float(n),
            distance_nm=0.0,
        )
    return routes


def _wind_snapshot(run_dir: Path) -> xr.Dataset | None:
    """Rebuild a single-step CF Dataset from the t=0 wind snapshot."""
    path = run_dir / WIND_SNAPSHOT_NAME
    if not path.exists():
        return None
    with np.load(path) as snap:
        data = {
            name: snap[name][np.newaxis, :, :]
            for name in snap.files
            if name not in ("lats", "lons")
        }
        coords = {
            "time": ("time", np.zeros(1)),
            "latitude": ("latitude", snap["lats"]),
            "longitude": ("longitude", snap["lons"]),
        }
        return xr.Dataset(
            data_vars={
                name: (("time", "latitude", "longitude"), values)
                for name, values in data.items()
            },
            coords=coords,
        )


def summarize(run_dir: Path) -> Path:
    """Re-render plots and print the summary table from a run directory."""
    manifest = json.loads((run_dir / MANIFEST_NAME).read_text())
    rows = _rows_from_csv(run_dir)
    routes = _routes_from_gpx(run_dir)
    grid = _wind_snapshot(run_dir)

    from .staircase import StaircaseResult

    result = StaircaseResult(
        rows=rows, reference=routes.get("reference", _empty_route())
    )

    plot_tracks(run_dir / "plot_tracks.png", routes, grid)
    plot_degradation(run_dir / "plot_degradation.png", result)
    plot_size_fidelity(run_dir / "plot_size_fidelity.png", result)

    print(f"scenario: {manifest['scenario']}")
    checksum = manifest["data_checksum"][:12]
    print(f"code version: {manifest['code_version']}  data checksum: {checksum}...")
    from .staircase import format_summary

    print(format_summary(rows))
    print(f"\nre-rendered plots in {run_dir}")
    return run_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m light_router.summarize <run_dir>``."""
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("usage: python -m light_router.summarize <run_dir>", file=sys.stderr)
        return 2
    run_dir = Path(argv[0])
    if not (run_dir / MANIFEST_NAME).exists():
        print(f"not a run directory: {run_dir}", file=sys.stderr)
        return 1
    summarize(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
