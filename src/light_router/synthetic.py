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
) -> WeatherGrid:
    """Uniform trade-wind field with a slow temporal modulation.

    Wind blows FROM `direction_from_deg` (meteorological convention).
    Speed varies smoothly in time so temporal downsampling has a measurable
    cost. Deterministic: no randomness.
    """
    nt, nlat, nlon = len(times), len(lats), len(lons)
    speed = mean_speed_kt * (1.0 + 0.15 * np.sin(2 * np.pi * times / 48.0))
    speed = np.broadcast_to(speed[:, None, None], (nt, nlat, nlon)).copy()
    direction = np.broadcast_to(
        np.full((1, 1, 1), direction_from_deg), (nt, nlat, nlon)
    )

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


def add_storm(
    field: WeatherGrid,
    center: tuple[float, float] = (22.5, -19.0),
    radius_deg: float = 2.5,
    strength_ms: float = 15.0,
    period_hours: float = 36.0,
) -> WeatherGrid:
    """Overlay a compact storm pulsing in time; returns a new grid.

    The storm wind blows toward the NE (opposing the trade-wind track), so
    with the default center it sits on the direct Canary -> Cape Verde route
    and the router must dodge it. Coarse spatial sampling smears or misplaces
    the dodge, which is what makes the degradation curve measurable — smooth
    fields degrade for free. Deterministic: no randomness.
    """
    lats, lons, times = field.lats, field.lons, field.times
    d = np.sqrt((lats[:, None] - center[0]) ** 2 + (lons[None, :] - center[1]) ** 2)
    mask = np.exp(-((d / radius_deg) ** 2))
    pulse = 0.5 + 0.5 * np.sin(2 * np.pi * times / period_hours)
    storm = (mask[None, :, :] * pulse[:, None, None]).astype(np.float32)
    data = {
        name: ((1.0 - storm) * arr + storm * strength_ms).astype(np.float32)
        for name, arr in field.data.items()
    }
    return WeatherGrid(times=times, lats=lats, lons=lons, data=data)
