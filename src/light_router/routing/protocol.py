"""The Router protocol: the seam every router implements (Compatibility rule 2).

``route(start, finish, start_time) -> Route`` is the entire contract: the
Level 1 oracle must be replaceable by an external reference router (a pinned
subprocess adapter) without changing the harness. A router is bound to its
weather at construction — see ``RouterFactory``.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

import xarray as xr

from light_router.models.route import Route


@runtime_checkable
class Router(Protocol):
    """The routing interface every router implements (Compatibility rule 2)."""

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route: ...


RouterFactory = Callable[[xr.Dataset], Router]
"""Binds a weather dataset to a Router (Compatibility rule 2).

Defined once here, next to the Router protocol it produces; the harness
(``harness.staircase``), the episode wrapper (``simulation.scenario``) and
the oracle adapter all share this type. For the oracle, the factory writes
the dataset to disk and drives the pinned subprocess; for the surrogate,
it builds an ``IsochroneRouter`` in-process.
"""
