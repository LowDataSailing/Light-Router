"""Sample weather (or any gridded data) along a route's waypoints.

A router outputs a plan — waypoints, never weather beliefs (Decision
#22). These utilities link a :class:`~light_router.models.route.Route`
(or bare waypoint arrays) to a
:class:`~light_router.models.weather.WeatherGrid`, so metrics, exports
and plots can attach the wind a route was planned against, or actually
sailed through.
"""

from __future__ import annotations

import numpy as np

from light_router.models.route import Route
from light_router.models.weather import WeatherGrid


def wind_along_route(grid: WeatherGrid, route: Route) -> tuple[np.ndarray, np.ndarray]:
    """True wind speed (kt) and angle (deg) at each waypoint of a route.

    The wind is sampled at ``(waypoint.time, waypoint.lat, waypoint.lon)``
    on ``grid``. TWA is the absolute angle between the arriving leg's
    heading and the wind direction (0 = dead upwind, 180 = dead
    downwind); NaN at the start waypoint, where no leg arrives.

    Returns:
        ``(tws, twa)`` — one value per waypoint, NaN-padded at the start.
    """
    return wind_along_track(grid, route.lat, route.lon, route.time)


def wind_along_track(
    grid: WeatherGrid,
    lat: np.ndarray,
    lon: np.ndarray,
    time: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """True wind speed (kt) and angle (deg) along a bare track.

    The track is one position per time step (e.g. a simulated passage's
    actual track); TWA at each point uses the heading of the leg arriving
    there, NaN at the first point.
    """
    tws, wind_from = grid.wind(time, lat, lon)
    n = len(lat)
    heading = np.full(n, np.nan)
    if n >= 2:
        from light_router.geo import initial_bearing

        heading[1:] = initial_bearing(lat[:-1], lon[:-1], lat[1:], lon[1:])
    twa = np.abs(heading - wind_from) % 360.0
    twa = np.where(twa > 180.0, 360.0 - twa, twa)
    return np.asarray(tws, dtype=float), np.asarray(twa, dtype=float)
