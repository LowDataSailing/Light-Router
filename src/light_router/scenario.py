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

from .isochrone import IsochroneRouter, Router, RouterConfig, RouterFactory
from .polar import PolarTable
from .staircase import STAIRCASE, StaircaseResult, run_staircase


@dataclass
class Scenario:
    """One routing scenario: weather + endpoints + experiment config."""

    weather: xr.Dataset  # canonical CF dataset (the episode's world)
    start: tuple[float, float]
    finish: tuple[float, float]
    start_time: float = 0.0  # hours since forecast initialization
    staircase: list[int | None] = field(default_factory=lambda: list(STAIRCASE))

    def run(self, router_factory: RouterFactory) -> StaircaseResult:
        """Run the degradation staircase for this scenario (the episode)."""
        return run_staircase(
            self.weather,
            router_factory,
            self.start,
            self.finish,
            self.staircase,
            start_time=self.start_time,
        )


def surrogate_router_factory(
    polar: PolarTable,
    config: RouterConfig | None = None,
) -> RouterFactory:
    """Router factory for the in-repo provisional isochrone surrogate.

    The oracle replacement is the same shape: a callable that binds a
    weather dataset to a Router (for the oracle, an adapter that writes the
    dataset to disk and drives the pinned subprocess).
    """
    cfg = config if config is not None else RouterConfig()

    def factory(weather: xr.Dataset) -> Router:
        return IsochroneRouter.from_dataset(weather, polar, cfg)

    return factory
