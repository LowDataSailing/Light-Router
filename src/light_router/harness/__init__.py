"""The benchmark harness: degrade, re-route, measure.

``degrade`` is the bandwidth pipeline, ``staircase`` is the budget-staircase
experiment runner, ``metrics`` is the route-quality comparison. The harness
speaks the canonical CF Dataset and the Router protocol, so the oracle is
swappable without touching it.
"""

from light_router.harness.degrade import (
    DegradeConfig,
    best_config_for_budget,
    candidate_configs,
    degrade,
    package_size,
)
from light_router.harness.metrics import RouteMetrics, compare_routes
from light_router.harness.staircase import (
    STAIRCASE,
    StaircaseResult,
    StaircaseRow,
    budget_label,
    format_summary,
    run_staircase,
    write_csv,
)

__all__ = [
    "DegradeConfig",
    "RouteMetrics",
    "STAIRCASE",
    "StaircaseResult",
    "StaircaseRow",
    "best_config_for_budget",
    "budget_label",
    "candidate_configs",
    "compare_routes",
    "degrade",
    "format_summary",
    "package_size",
    "run_staircase",
    "write_csv",
]
