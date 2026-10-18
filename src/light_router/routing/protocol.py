"""The Router protocol: the seam every router implements (Compatibility rule 2).

``route(start, finish, start_time) -> Route`` is the entire routing
contract; ``for_weather(weather) -> Router`` is the binding: one router
setup (polar, config, pin, ...) is re-bound to each weather dataset the
harness hands it — the degraded package of every budget level, the
oracle's subprocess inputs. There is no separate factory layer: the
router object carries its own configuration as attributes and knows how
to rebind itself (Decision #22).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Protocol, runtime_checkable

import xarray as xr

from light_router.models.route import Route


@runtime_checkable
class Router(Protocol):
    """The routing interface every router implements (Compatibility rule 2)."""

    name: str
    """Algorithm identity for run manifests — e.g.
    ``isochrone-surrogate``; oracle adapters carry their pin here."""

    def for_weather(self, weather: xr.Dataset) -> Router:
        """Bind this router's setup to a weather dataset.

        Returns a router that routes on ``weather``; the setup (polar,
        config, pin, ...) is carried over. For the oracle this writes
        the dataset to disk and prepares the pinned subprocess; for
        in-process routers it is a re-construction.
        """
        ...

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route: ...


class BaseRouter(ABC):
    """Nominal base class for routers we own.

    The ``Router`` protocol is the seam: anything with a matching
    ``route()`` and ``for_weather()`` satisfies it structurally —
    including the oracle subprocess adapter, which must not inherit from
    our code. ``BaseRouter`` is the concrete-side counterpart for
    in-repo algorithms: subclass it to get the validated contract
    nominally. A ``BaseRouter`` subclass is a ``Router`` by
    construction; the protocol check stays the harness's only assumption.
    """

    name: str
    """Algorithm identity for run manifests — the class name by default;
    subclasses override with their published identity (e.g.
    ``"isochrone-surrogate"``)."""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "name" not in cls.__dict__:
            cls.name = cls.__name__

    def for_weather(self, weather: xr.Dataset) -> BaseRouter:
        """Re-bind to a new weather dataset.

        The default replaces the ``grid`` field (dataclasses.replace on a
        :class:`~light_router.models.weather.WeatherGrid` built from the
        CF dataset) — enough for in-process routers whose binding is just
        the grid. Override when binding is heavier: the oracle writes the
        dataset to disk and drives its pinned subprocess.
        """
        from light_router.dataset import grid_from_dataset

        return replace(self, grid=grid_from_dataset(weather))  # type: ignore[type-var,arg-type]

    @abstractmethod
    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route: ...
