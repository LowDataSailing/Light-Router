"""Light Router — communication-constrained, vessel-conditioned weather routing.

Goal 1 prototype: Level 1 isochrone baseline + bandwidth-quality
degradation harness. See specs/goal-1-baseline.md and
specs/compatibility-principles.md.

Public interface (Compatibility rules 1 and 2): weather flows in as a
CF-compliant xarray Dataset, routing goes through the Router protocol, and
``WeatherGrid`` (the transitional internal numpy view) is not exported.

Package layout:

- ``models`` — domain data structures (weather grid, vessel polar, route,
  degradation config, experiment and passage records)
- ``routing`` — the Router seam (``protocol``) and the in-repo isochrone
  surrogate adapter
- ``harness`` — the degradation pipeline, budget staircase, and metrics
- ``simulation`` — the episode semantics and the operational passage mimic
- ``weather_data`` — acquisition clients, the GRIB loader, the shared
  downloader, and experiment data packs
- ``reporting`` — run directories, GPX/GeoJSON export, plots, summarize
"""

from light_router.dataset import to_cf_dataset
from light_router.harness.metrics import RouteMetrics, compare_routes
from light_router.harness.staircase import (
    STAIRCASE,
    StaircaseResult,
    run_staircase,
    write_csv,
)
from light_router.models.vessel import PolarTable, synthetic_cruising_polar
from light_router.reporting.artifacts import write_artifacts
from light_router.routing import IsochroneRouter, Route, Router, RouterConfig
from light_router.simulation.scenario import Scenario, surrogate_router_factory

__version__ = "0.1.0"

__all__ = [
    "IsochroneRouter",
    "PolarTable",
    "Route",
    "RouteMetrics",
    "Router",
    "RouterConfig",
    "STAIRCASE",
    "Scenario",
    "StaircaseResult",
    "compare_routes",
    "run_staircase",
    "surrogate_router_factory",
    "synthetic_cruising_polar",
    "to_cf_dataset",
    "write_artifacts",
    "write_csv",
]
