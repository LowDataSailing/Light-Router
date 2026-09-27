"""Deterministic synthetic weather fields for tests and offline demos."""

from __future__ import annotations

import numpy as np

from .weather import WeatherGrid


def trade_wind_field(
    lats: np.ndarray,
    lons: np.ndarray,
    times: np.ndarray,
    mean_speed_kt: float = 15.0,
    direction_from_deg: float = 60.0,
    shear_deg: float = 0.0,
) -> WeatherGrid:
    """Uniform trade-wind field with a slow temporal modulation.

    Wind blows FROM `direction_from_deg` (meteorological convention).
    Speed varies smoothly in time so temporal downsampling has a measurable
    cost. Deterministic: no randomness.
    """
    nt, nlat, nlon = len(times), len(lats), len(lons)
    speed = mean_speed_kt * (1.0 + 0.15 * np.sin(2 * np.pi * times / 48.0))
    speed = np.broadcast_to(speed[:, None, None], (nt, nlat, nlon)).copy()
    direction = direction_from_deg + shear_deg * (lats[None, :, None] - lats[0]) / max(
        lats[-1] - lats[0], 1e-9
    )
    direction = np.broadcast_to(direction, (nt, nlat, nlon))

    speed_ms = speed / 1.94384
    # "from" direction -> vector components of wind flow
    u = -speed_ms * np.sin(np.radians(direction))
    v = -speed_ms * np.cos(np.radians(direction))
    return WeatherGrid(
        times=times,
        lats=lats,
        lons=lons,
        data={"u10": u.astype(np.float32), "v10": v.astype(np.float32)},
    )


def storm_field(
    lats: np.ndarray,
    lons: np.ndarray,
    times: np.ndarray,
    storm_center: tuple[float, float] = (40.0, -25.0),
    storm_radius_deg: float = 6.0,
    background_kt: float = 15.0,
) -> WeatherGrid:
    """Background trades with a rotating storm system (for the storm-avoidance
    scenario shape). Wind speed peaks at the storm center."""
    nt, nlat, nlon = len(times), len(lats), len(lons)
    lat_grid = lats[None, :, None]
    lon_grid = lons[None, None, :]
    # storm drifts eastward over time
    center_lat = storm_center[0]
    center_lon = storm_center[1] + 0.15 * times[:, None, None]
    d = np.sqrt(
        (lat_grid - center_lat) ** 2 + (lat_grid * 0.0 + lon_grid - center_lon) ** 2
    )
    storm_mask = np.exp(-((d / storm_radius_deg) ** 2))
    storm_mask = np.broadcast_to(storm_mask, (nt, nlat, nlon))

    speed = background_kt * (1.0 + 0.15 * np.sin(2 * np.pi * times / 48.0))
    speed = np.broadcast_to(speed[:, None, None], (nt, nlat, nlon)).copy()
    speed = speed + 30.0 * storm_mask  # up to ~45 kt in the core
    # background from NE; storm wind direction swirls around the center
    direction = 60.0 + 180.0 * storm_mask  # crude: reversed inside the core
    direction = np.broadcast_to(direction, (nt, nlat, nlon)).copy()

    speed_ms = speed / 1.94384
    u = -speed_ms * np.sin(np.radians(direction))
    v = -speed_ms * np.cos(np.radians(direction))
    return WeatherGrid(
        times=times,
        lats=lats,
        lons=lons,
        data={"u10": u.astype(np.float32), "v10": v.astype(np.float32)},
    )
