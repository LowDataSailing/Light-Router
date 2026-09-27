"""Great-circle geometry helpers (nautical units: nautical miles, degrees)."""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles


def great_circle_distance(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray | float:
    """Great-circle distance in nautical miles (haversine)."""
    phi1, lam1 = (
        np.radians(np.asarray(lat1, dtype=float)),
        np.radians(np.asarray(lon1, dtype=float)),
    )
    phi2, lam2 = (
        np.radians(np.asarray(lat2, dtype=float)),
        np.radians(np.asarray(lon2, dtype=float)),
    )
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_NM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def initial_bearing(
    lat1: np.ndarray | float,
    lon1: np.ndarray | float,
    lat2: np.ndarray | float,
    lon2: np.ndarray | float,
) -> np.ndarray | float:
    """Initial great-circle bearing from point 1 to point 2, degrees [0, 360)."""
    phi1, lam1 = (
        np.radians(np.asarray(lat1, dtype=float)),
        np.radians(np.asarray(lon1, dtype=float)),
    )
    phi2, lam2 = (
        np.radians(np.asarray(lat2, dtype=float)),
        np.radians(np.asarray(lon2, dtype=float)),
    )
    dlam = lam2 - lam1
    y = np.sin(dlam) * np.cos(phi2)
    x = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlam)
    theta = np.degrees(np.arctan2(y, x))
    return np.mod(theta, 360.0)


def destination(
    lat: np.ndarray | float,
    lon: np.ndarray | float,
    bearing_deg: np.ndarray | float,
    distance_nm: np.ndarray | float,
) -> tuple[np.ndarray | float, np.ndarray | float]:
    """Destination point given start, initial bearing (deg) and distance (nm)."""
    phi1, lam1 = (
        np.radians(np.asarray(lat, dtype=float)),
        np.radians(np.asarray(lon, dtype=float)),
    )
    theta = np.radians(np.asarray(bearing_deg, dtype=float))
    d = np.asarray(distance_nm, dtype=float) / EARTH_RADIUS_NM
    phi2 = np.arcsin(
        np.sin(phi1) * np.cos(d) + np.cos(phi1) * np.sin(d) * np.cos(theta)
    )
    lam2 = lam1 + np.arctan2(
        np.sin(theta) * np.sin(d) * np.cos(phi1),
        np.cos(d) - np.sin(phi1) * np.sin(phi2),
    )
    return np.degrees(phi2), np.mod(np.degrees(lam2) + 540.0, 360.0) - 180.0
