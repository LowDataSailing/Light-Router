"""Simulation: the episode semantics and the operational passage mimic.

``scenario`` fixes the Gymnasium-style episode naming (Compatibility rule
3); ``simulate`` is the real-router mimic — replan on degraded forecasts
every cycle, sail on the measured truth.
"""

from __future__ import annotations

from experiments.models.passage import CycleRecord, PassageResult
from light_router.models.forecast import ForecastCycle
from experiments.simulation.scenario import Scenario, surrogate_router_factory
from experiments.simulation.simulate import (
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
