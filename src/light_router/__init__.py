"""Light Router — communication-constrained, vessel-conditioned weather routing.

Goal 1 prototype: Level 1 isochrone baseline + bandwidth-quality
degradation harness. See specs/goal-1-baseline.md.
"""

from .artifacts import write_artifacts
from .degrade import DegradeConfig, best_config_for_budget, degrade, package_size
from .isochrone import IsochroneRouter, Route, RouterConfig
from .metrics import RouteMetrics, compare_routes
from .polar import PolarTable, synthetic_cruising_polar
from .staircase import STAIRCASE, StaircaseResult, run_staircase, write_csv
from .weather import WeatherGrid

__version__ = "0.1.0"

__all__ = [
    "DegradeConfig",
    "IsochroneRouter",
    "PolarTable",
    "Route",
    "RouteMetrics",
    "RouterConfig",
    "STAIRCASE",
    "StaircaseResult",
    "WeatherGrid",
    "best_config_for_budget",
    "compare_routes",
    "degrade",
    "package_size",
    "run_staircase",
    "synthetic_cruising_polar",
    "write_artifacts",
    "write_csv",
]
