"""Simulation: the episode semantics and the operational passage mimic.

``scenario`` fixes the Gymnasium-style episode naming (Compatibility rule
3); ``simulate`` is the real-router mimic — replan on degraded forecasts
every cycle, sail on the measured truth.
"""

from light_router.models.passage import CycleRecord, ForecastCycle, PassageResult
from light_router.simulation.scenario import Scenario, surrogate_router_factory
from light_router.simulation.simulate import (
    format_operational_summary,
    run_operational_staircase,
    simulate_passage,
)

__all__ = [
    "CycleRecord",
    "ForecastCycle",
    "PassageResult",
    "Scenario",
    "format_operational_summary",
    "run_operational_staircase",
    "simulate_passage",
    "surrogate_router_factory",
]
