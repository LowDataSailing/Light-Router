"""Light Router — communication-constrained, vessel-conditioned weather routing.

The library is the router stack: what would actually run on a boat. Weather
flows in as a CF-compliant xarray Dataset from standard protocols
(Compatibility rule 1), routing goes through the Router protocol (rule 2),
and ``WeatherGrid`` (the transitional internal numpy view) is not exported.

The virtual world — degradation harness, passage simulation, run reporting,
synthetic fixtures — lives in ``experiments/`` at the repo root, not in this
package. Experiments import from the library; never the other way around.

Package layout:

- ``models`` — domain data structures (weather grid, vessel polar, route,
  forecast cycles)
- ``routing`` — the Router seam (``protocol``: ``Router`` + ``BaseRouter``)
  and the in-repo isochrone surrogate adapter
- ``weather_data`` — acquisition clients, the GRIB loader, the shared
  downloader, and experiment data packs
"""

from __future__ import annotations

from light_router.dataset import to_cf_dataset
from light_router.models.forecast import ForecastCycle
from light_router.models.vessel import PolarTable
from light_router.routing import (
    BaseRouter,
    IsochroneRouter,
    Route,
    Router,
    RouterConfig,
)

__version__ = "0.1.0"

__all__ = [
    "BaseRouter",
    "ForecastCycle",
    "IsochroneRouter",
    "PolarTable",
    "Route",
    "Router",
    "RouterConfig",
    "to_cf_dataset",
]
