"""Domain models: the data structures the router stack speaks.

Grouped by concept: the environment (``weather``), the boat (``vessel``),
the plan (``route``), and the forecast runs the router consumes
(``forecast``). The experiment-domain records (degradation configs,
staircase and passage results) live in ``experiments/models/``.
"""

from __future__ import annotations

from light_router.models.forecast import ForecastCycle
from light_router.models.route import (
    Route,
    RouterConfig,
    Waypoint,
    mean_vmg,
    route_bearing,
)
from light_router.models.vessel import PolarTable
from light_router.models.weather import route_grid_box

__all__ = [
    "ForecastCycle",
    "PolarTable",
    "Route",
    "RouterConfig",
    "Waypoint",
    "mean_vmg",
    "route_bearing",
    "route_grid_box",
]
