"""Surrogate validation harness: the isochrone surrogate's bias vs an oracle.

Runs the in-repo isochrone surrogate and an oracle adapter on the same
scenario (by default the synthetic trade-wind field) and reports the
surrogate's bias in ETA, sailed distance and track divergence — the
measurement that decides whether the surrogate may keep labeling the
harness's reference routes (Decision #15).

The comparison direction is oracle -> surrogate: a positive ETA bias means
the surrogate arrives later than the oracle. Metrics are the harness's own
``compare_routes`` axes, reported separately, never combined. The harness
works with whichever oracle is available — libweatherrouting live from the
optional ``oracle`` group, OpenCPN when the pinned binary exists — and
degrades to an honest "no oracle" report when neither is installed.

Run as a script: ``uv run python -m experiments.oracle.validate``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from light_router.dataset import grid_from_dataset, to_cf_dataset
from light_router.models.vessel import PolarTable
from light_router.routing import IsochroneRouter
from light_router.routing.protocol import Router
from experiments.harness.metrics import compare_routes
from experiments.oracle.libweatherrouting import LibWeatherRoutingRouter
from experiments.oracle.opencpn import OpenCPNRouter
from experiments.synthetic import trade_wind_field
from experiments.synthetic_polar import synthetic_cruising_polar

OPENCPN_BINARY_ENV = "LR_ORACLE_OPENCPN_BINARY"
"""Environment variable pointing at the pinned OpenCPN oracle binary."""

VALIDATION_START = (28.0, -15.5)
"""Default scenario start: Las Palmas, Canary Islands (deg)."""

VALIDATION_FINISH = (16.75, -22.9)
"""Default scenario finish: Mindelo, Cape Verde (deg)."""

SURROGATE_NAME = "IsochroneRouter"
"""Identity of the in-repo router under validation."""


def validation_weather() -> xr.Dataset:
    """Synthetic trade-wind field covering the default validation passage."""
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 121.0, 6.0)
    return to_cf_dataset(trade_wind_field(lats, lons, times))


def validate_surrogate(
    weather: xr.Dataset,
    start: tuple[float, float],
    finish: tuple[float, float],
    polar: PolarTable,
    oracle: Router,
    surrogate_kwargs: dict[str, Any] | None = None,
    start_time: float = 0.0,
) -> dict[str, Any]:
    """Route one scenario with the surrogate and an oracle; report the bias.

    The oracle is the reference side of ``compare_routes``; the returned
    dict carries both raw ETAs/distances and the bias axes. When the oracle
    does not reach the finish there is no reference to compare against, so
    the report says so instead of inventing numbers.
    """
    surrogate = IsochroneRouter.from_dataset(weather, polar, **(surrogate_kwargs or {}))
    oracle = oracle.for_weather(weather)

    surrogate_route = surrogate.route(start, finish, start_time)
    oracle_route = oracle.route(start, finish, start_time)

    report: dict[str, Any] = {
        "oracle": oracle.name,
        "surrogate": SURROGATE_NAME,
        "oracle_reached": bool(oracle_route.reached),
        "surrogate_reached": bool(surrogate_route.reached),
        "oracle_eta_hours": float(oracle_route.eta_hours),
        "surrogate_eta_hours": float(surrogate_route.eta_hours),
        "oracle_distance_nm": float(oracle_route.distance_nm),
        "surrogate_distance_nm": float(surrogate_route.distance_nm),
        "oracle_track_waypoints": int(oracle_route.n_waypoints),
        "surrogate_track_waypoints": int(surrogate_route.n_waypoints),
    }
    if not oracle_route.reached:
        report["reason"] = "oracle did not reach the finish; no reference"
        return report
    if not surrogate_route.reached:
        report["reason"] = "surrogate did not reach the finish"
        return report

    grid = grid_from_dataset(weather)
    metrics = compare_routes(oracle_route, surrogate_route, finish, grid, grid)
    report.update(
        {
            "eta_bias_pct": metrics.eta_diff_pct,
            "distance_bias_pct": metrics.distance_diff_pct,
            "vmg_bias_kt": metrics.vmg_diff_kt,
            "max_wind_diff_kt": metrics.max_wind_diff_kt,
            "decision_divergence": metrics.decision_divergence,
            "initial_bearing_diff_deg": metrics.initial_bearing_diff_deg,
            "geographic_divergence_nm": metrics.geographic_divergence_nm,
        }
    )
    return report


def available_oracles(
    polar: PolarTable,
    opencpn_binary: Path | None = None,
) -> list[tuple[str, Router]]:
    """Oracle routers usable right now, in preference order.

    Each entry is a display name and an unbound router setup; the caller
    binds it to the scenario weather via ``for_weather``. libweatherrouting
    counts as available when the optional ``oracle`` group is installed;
    OpenCPN when a binary path is configured (argument or
    ``LR_ORACLE_OPENCPN_BINARY``) and exists. Anything missing is skipped —
    the caller's report states what ran and what did not.
    """
    oracles: list[tuple[str, Router]] = []
    try:
        import weatherrouting  # noqa: F401

        oracles.append(("libweatherrouting", LibWeatherRoutingRouter(polar=polar)))
    except ImportError:
        pass

    binary = opencpn_binary
    if binary is None and os.environ.get(OPENCPN_BINARY_ENV):
        binary = Path(os.environ[OPENCPN_BINARY_ENV])
    if binary is not None and binary.exists():
        oracles.append(
            ("opencpn-weather-routing", OpenCPNRouter(binary=binary, polar=polar))
        )
    return oracles


def format_report(report: dict[str, Any]) -> str:
    """Human-readable bias report (the console summary)."""
    lines = [
        "Surrogate vs oracle bias "
        f"({report['scenario']['start']} -> {report['scenario']['finish']})",
        f"{'oracle':<44} {'o-eta(h)':>9} {'s-eta(h)':>9} "
        f"{'eta%':>7} {'dist%':>7} {'geo nm':>7} {'decision':>9}",
    ]
    for entry in report["oracles"]:
        if not entry.get("oracle_reached", False):
            lines.append(
                f"{entry['oracle']:<44} {'-':>9} "
                f"{entry['surrogate_eta_hours']:>9.1f} "
                f"{'-':>7} {'-':>7} {'-':>7} {'-':>9}"
            )
            continue
        eta = f"{entry['eta_bias_pct']:+.1f}" if "eta_bias_pct" in entry else "-"
        dist = (
            f"{entry['distance_bias_pct']:+.1f}"
            if "distance_bias_pct" in entry
            else "-"
        )
        geo = (
            f"{entry['geographic_divergence_nm']:.1f}"
            if "geographic_divergence_nm" in entry
            else "-"
        )
        decision = (
            str(entry["decision_divergence"]) if "decision_divergence" in entry else "-"
        )
        lines.append(
            f"{entry['oracle']:<44} {entry['oracle_eta_hours']:>9.1f} "
            f"{entry['surrogate_eta_hours']:>9.1f} {eta:>7} {dist:>7} "
            f"{geo:>7} {decision:>9}"
        )
    if not report["oracles"]:
        lines.append(f"no oracle available: {report['reason']}")
    return "\n".join(lines)


def run_validation(
    polar: PolarTable | None = None,
    oracles: list[tuple[str, Router]] | None = None,
    output: Path | None = None,
    opencpn_binary: Path | None = None,
    surrogate_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the default validation scenario against every available oracle.

    ``oracles`` overrides oracle discovery (each entry is a display name
    and an unbound router setup); None discovers what is installed. The
    report is printed, written as JSON to ``output`` when given, and
    returned.
    """
    polar = polar if polar is not None else synthetic_cruising_polar()
    weather = validation_weather()
    start, finish = VALIDATION_START, VALIDATION_FINISH

    if oracles is None:
        oracles = available_oracles(polar, opencpn_binary)

    report: dict[str, Any] = {
        "scenario": {
            "weather": "synthetic trade wind (experiments.synthetic)",
            "start": list(start),
            "finish": list(finish),
            "start_time_hours": 0.0,
        },
        "surrogate": SURROGATE_NAME,
        "oracles": [],
    }
    for _name, oracle in oracles:
        report["oracles"].append(
            validate_surrogate(
                weather,
                start,
                finish,
                polar,
                oracle,
                surrogate_kwargs=surrogate_kwargs,
            )
        )
    if not oracles:
        report["reason"] = (
            "no oracle available: install the optional 'oracle' group "
            "(libweatherrouting) or point LR_ORACLE_OPENCPN_BINARY at the "
            "pinned OpenCPN build"
        )

    print(format_report(report))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    """CLI entry: validate the surrogate against the available oracles."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Quantify the isochrone surrogate's bias against an "
        "oracle reference router on the synthetic trade-wind scenario."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="path to write the bias report as JSON",
    )
    parser.add_argument(
        "--opencpn-binary",
        type=Path,
        default=None,
        help="path of the pinned OpenCPN oracle binary "
        f"(default: ${OPENCPN_BINARY_ENV})",
    )
    args = parser.parse_args()
    run_validation(output=args.output, opencpn_binary=args.opencpn_binary)


if __name__ == "__main__":
    main()
