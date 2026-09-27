"""4D weather grid with bilinear spatial and linear temporal interpolation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .geo import great_circle_distance


@dataclass
class WeatherGrid:
    """Weather field on a regular lat/lon grid with a time axis.

    times: hours since the scenario start (strictly increasing).
    lats / lons: strictly increasing coordinate axes (degrees).
    data: variable name -> array of shape (nt, nlat, nlon).
    """

    times: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    data: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.times.ndim != 1 or len(self.times) < 1:
            raise ValueError("times must be a 1D array with at least one step")
        if self.lats.ndim != 1 or self.lons.ndim != 1:
            raise ValueError("lats and lons must be 1D arrays")
        if not (
            np.all(np.diff(self.times) > 0)
            and np.all(np.diff(self.lats) > 0)
            and np.all(np.diff(self.lons) > 0)
        ):
            raise ValueError("times, lats and lons must be strictly increasing")
        for name, arr in self.data.items():
            if arr.shape != (len(self.times), len(self.lats), len(self.lons)):
                raise ValueError(
                    f"variable {name!r} has shape {arr.shape}, expected "
                    f"{(len(self.times), len(self.lats), len(self.lons))}"
                )

    @property
    def variables(self) -> list[str]:
        return sorted(self.data)

    def sample(
        self, t_hours: np.ndarray, lat: np.ndarray, lon: np.ndarray, variable: str
    ) -> np.ndarray:
        """Sample a variable at (time [h], lat, lon) points, bilinear in space,
        linear in time. Points outside the grid are clamped to the edges."""
        arr = self.data[variable]
        t = self._clamp(np.asarray(t_hours, dtype=float), self.times)
        lat_c = self._clamp(np.asarray(lat, dtype=float), self.lats)
        lon_c = self._clamp(np.asarray(lon, dtype=float), self.lons)

        t0, t1, tw = self._interp_indices(t, self.times)
        lat0, lat1, latw = self._interp_indices(lat_c, self.lats)
        lon0, lon1, lonw = self._interp_indices(lon_c, self.lons)

        corner = lambda ti, la, lo: arr[ti, la, lo]  # noqa: E731
        top = corner(t0, lat0, lon0) * (1 - lonw) + corner(t0, lat0, lon1) * lonw
        bot = corner(t0, lat1, lon0) * (1 - lonw) + corner(t0, lat1, lon1) * lonw
        plane0 = top * (1 - latw) + bot * latw
        top = corner(t1, lat0, lon0) * (1 - lonw) + corner(t1, lat0, lon1) * lonw
        bot = corner(t1, lat1, lon0) * (1 - lonw) + corner(t1, lat1, lon1) * lonw
        plane1 = top * (1 - latw) + bot * latw
        return plane0 * (1 - tw) + plane1 * tw

    def wind(
        self, t_hours: np.ndarray, lat: np.ndarray, lon: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Wind speed (kt) and direction (deg, direction wind comes FROM) at points."""
        if "u10" not in self.data or "v10" not in self.data:
            raise KeyError("wind requires variables 'u10' and 'v10'")
        u = self.sample(t_hours, lat, lon, "u10")
        v = self.sample(t_hours, lat, lon, "v10")
        # u/v are in m/s (GFS convention); convert to knots.
        u_kt, v_kt = u * 1.94384, v * 1.94384
        speed = np.sqrt(u_kt**2 + v_kt**2)
        # Meteorological "from" direction: direction the wind blows FROM.
        direction = np.mod(270.0 - np.degrees(np.arctan2(v_kt, u_kt)), 360.0)
        return speed, direction

    def grid_extent(self) -> tuple[float, float, float, float]:
        return (
            float(self.lons[0]),
            float(self.lons[-1]),
            float(self.lats[0]),
            float(self.lats[-1]),
        )

    @staticmethod
    def _clamp(values: np.ndarray, axis: np.ndarray) -> np.ndarray:
        return np.clip(values, axis[0], axis[-1])

    @staticmethod
    def _interp_indices(
        values: np.ndarray, axis: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Indices (i0, i1) bracketing each value and the weight of i1."""
        i1 = np.clip(np.searchsorted(axis, values, side="left"), 1, len(axis) - 1)
        i0 = i1 - 1
        span = axis[i1] - axis[i0]
        weight = np.where(span > 0, (values - axis[i0]) / span, 0.0)
        return i0, i1, np.clip(weight, 0.0, 1.0)


def route_grid_box(
    start: tuple[float, float], finish: tuple[float, float], margin_deg: float = 2.0
) -> tuple[float, float, float, float]:
    """Bounding box (lon_min, lon_max, lat_min, lat_max) covering start->finish."""
    lat_min, lat_max = sorted((start[0], finish[0]))
    lon_min, lon_max = sorted((start[1], finish[1]))
    return (
        lon_min - margin_deg,
        lon_max + margin_deg,
        lat_min - margin_deg,
        lat_max + margin_deg,
    )


def grid_resolution_nm(lats: np.ndarray) -> float:
    """Mean meridional grid resolution in nautical miles."""
    if len(lats) < 2:
        raise ValueError("need at least two latitude steps")
    return float(
        np.mean(
            great_circle_distance(
                lats[:-1], np.zeros(len(lats) - 1), lats[1:], np.zeros(len(lats) - 1)
            )
        )
    )
