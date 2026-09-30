"""Routing: the Router seam and its adapters.

``protocol`` is the seam (Compatibility rule 2); ``isochrone`` is the
in-repo surrogate adapter. The future oracle subprocess is another adapter
over the same protocol.
"""

from light_router.models.route import Route, RouterConfig, mean_vmg, route_bearing
from light_router.routing.isochrone import IsochroneRouter
from light_router.routing.protocol import Router, RouterFactory

__all__ = [
    "IsochroneRouter",
    "Route",
    "Router",
    "RouterConfig",
    "RouterFactory",
    "mean_vmg",
    "route_bearing",
]
