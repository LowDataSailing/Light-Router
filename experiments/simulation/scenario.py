"""Scenario: the reproducible unit of experimentation — one episode.

Compatibility rule 3 (specs/compatibility-principles.md): first ML
iterations are supervised, so no environment loop is implemented yet — but
the semantics and naming are fixed now, so the Gymnasium adapter (Level 4
sequential-decision work) is a thin wrapper later:

- **scenario** = one scenario package (weather + config) = one **episode**
- **reset()** loads a scenario package (here: constructing a ``Scenario``)
- **step()** = one planning cycle: request data within budget -> receive
  the degraded package -> route (here: one staircase level)
- **observation** = the degraded weather package + vessel state
- **action** = the data request (adaptive acquisition; future work)
- **reward** = route quality vs the oracle reference (here: ``RouteMetrics``)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import xarray as xr

from light_router.routing import Router
from experiments.harness.staircase import STAIRCASE, StaircaseResult, run_staircase


@dataclass
class Scenario:
    """One routing scenario: weather + endpoints + experiment config."""

    weather: xr.Dataset  # canonical CF dataset (the episode's world)
    start: tuple[float, float]
    finish: tuple[float, float]
    start_time: float = 0.0  # hours since forecast initialization
    staircase: list[int | None] = field(default_factory=lambda: list(STAIRCASE))

    def run(self, router: Router) -> StaircaseResult:
        """Run the degradation staircase for this scenario (the episode).

        ``router`` is one router setup; the staircase re-binds it to the
        full-resolution weather and to every degraded package via
        ``for_weather``.
        """
        return run_staircase(
            self.weather,
            router,
            self.start,
            self.finish,
            self.staircase,
            start_time=self.start_time,
        )
