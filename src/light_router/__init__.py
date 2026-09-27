"""Light Router — communication-constrained, vessel-conditioned weather routing.

Goal 1 prototype: Level 1 isochrone baseline + bandwidth-quality
degradation harness. See specs/goal-1-baseline.md and
specs/compatibility-principles.md.

Public interface (Compatibility rules 1 and 2): weather flows in as a
CF-compliant xarray Dataset, routing goes through the Router protocol, and
``WeatherGrid`` (the transitional internal numpy view) is not exported.
"""

from .artifacts import write_artifacts
from .dataset import to_cf_dataset
from .isochrone import IsochroneRouter, Route, Router, RouterConfig
from .metrics import RouteMetrics, compare_routes
from .polar import PolarTable, synthetic_cruising_polar
from .scenario import Scenario, surrogate_router_factory
from .staircase import STAIRCASE, StaircaseResult, run_staircase, write_csv

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
