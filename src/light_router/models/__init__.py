"""Domain models: the data structures every layer speaks.

Grouped by concept: the environment (``weather``), the boat (``vessel``),
the plan (``route``), the data constraint (``degradation``), and the
experiment records (``experiment`` for the staircase, ``passage`` for the
operational simulation).
"""

from light_router.models.degradation import DegradeConfig, WIND_VARIABLES
from light_router.models.experiment import (
    RouteMetrics,
    StaircaseResult,
    StaircaseRow,
)
from light_router.models.passage import CycleRecord, ForecastCycle, PassageResult
from light_router.models.route import Route, RouterConfig, mean_vmg, route_bearing
from light_router.models.vessel import PolarTable, synthetic_cruising_polar
from light_router.models.weather import WeatherGrid, route_grid_box

__all__ = [
    "CycleRecord",
    "DegradeConfig",
    "ForecastCycle",
    "PassageResult",
    "PolarTable",
    "Route",
    "RouteMetrics",
    "RouterConfig",
    "StaircaseResult",
    "StaircaseRow",
    "WeatherGrid",
    "WIND_VARIABLES",
    "mean_vmg",
    "route_bearing",
    "route_grid_box",
    "synthetic_cruising_polar",
]
