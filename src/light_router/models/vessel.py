"""Boat polar diagram: boat speed as a function of true wind speed and angle.

Compatibility rule 5: polars load from industry-standard polar files
(OpenCPN-compatible CSV — first row = TWS values, first column = TWA
values, cells = boat speed in knots). The synthetic cruising polar is a
test fixture, not a research input.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class PolarTable:
    """Speed table over (TWS, TWA).

    tws: true wind speeds (kt), strictly increasing.
    twa: true wind angles (deg), strictly increasing, 0..180 (port tack only;
    gybe/tack symmetry mirrors the angle).
    speed: knots, shape (len(tws), len(twa)).
    """

    tws: np.ndarray
    twa: np.ndarray
    speed: np.ndarray

    def __post_init__(self) -> None:
        if self.tws.ndim != 1 or self.twa.ndim != 1:
            raise ValueError("tws and twa must be 1D arrays")
        if not (np.all(np.diff(self.tws) > 0) and np.all(np.diff(self.twa) > 0)):
            raise ValueError("tws and twa must be strictly increasing")
        if self.speed.shape != (len(self.tws), len(self.twa)):
            expected = (len(self.tws), len(self.twa))
            raise ValueError(f"speed has shape {self.speed.shape}, expected {expected}")
        if np.any(self.speed < 0):
            raise ValueError("polar speeds must be non-negative")

    def boat_speed(
        self, tws: np.ndarray | float, twa: np.ndarray | float
    ) -> np.ndarray | float:
        """Boat speed (kt) at the given true wind speed (kt) and angle (deg).

        TWA is the absolute angle between heading and wind direction; the table
        is symmetric across the wind (tack/gybe mirror).
        """
        tws_arr = np.asarray(tws, dtype=float)
        twa_arr = np.abs(np.asarray(twa, dtype=float)) % 360.0
        twa_arr = np.where(twa_arr > 180.0, 360.0 - twa_arr, twa_arr)
        tws_c = np.clip(tws_arr, self.tws[0], self.tws[-1])
        twa_c = np.clip(twa_arr, self.twa[0], self.twa[-1])

        i1 = np.clip(
            np.searchsorted(self.tws, tws_c, side="left"), 1, len(self.tws) - 1
        )
        j1 = np.clip(
            np.searchsorted(self.twa, twa_c, side="left"), 1, len(self.twa) - 1
        )
        i0, j0 = i1 - 1, j1 - 1
        ws = (tws_c - self.tws[i0]) / (self.tws[i1] - self.tws[i0])
        wa = (twa_c - self.twa[j0]) / (self.twa[j1] - self.twa[j0])
        ws = np.clip(ws, 0.0, 1.0)
        wa = np.clip(wa, 0.0, 1.0)

        s = self.speed
        v00 = s[i0, j0]
        v01 = s[i0, j1]
        v10 = s[i1, j0]
        v11 = s[i1, j1]
        result = (
            v00 * (1 - ws) * (1 - wa)
            + v01 * (1 - ws) * wa
            + v10 * ws * (1 - wa)
            + v11 * ws * wa
        )
        return result if np.ndim(tws) or np.ndim(twa) else float(result)

    @classmethod
    def from_polar_csv(cls, path: Path | str) -> PolarTable:
        """Load an OpenCPN-style polar CSV.

        Layout: first row = TWS values (kt), first column = TWA values
        (deg), cells = boat speed (kt). The top-left cell is ignored.
        """
        with open(path, newline="") as fh:
            rows = list(csv.reader(fh))
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            raise ValueError(f"polar CSV {path} is too small to be a polar table")
        tws = np.array([float(x) for x in rows[0][1:] if x.strip() != ""])
        twa = np.array([float(r[0]) for r in rows[1:] if r and r[0].strip() != ""])
        # CSV cells are laid out (TWA rows x TWS columns); the table stores
        # (TWS x TWA), so transpose
        speed = np.array(
            [[float(x) for x in r[1 : 1 + len(tws)]] for r in rows[1 : 1 + len(twa)]]
        ).T
        return cls(tws=tws, twa=twa, speed=speed)

    def to_polar_csv(self, path: Path | str) -> None:
        """Write the OpenCPN-style polar CSV (round-trips with from_polar_csv)."""
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["TWA\\TWS"] + [f"{v:g}" for v in self.tws])
            for j, angle in enumerate(self.twa):
                writer.writerow([f"{angle:g}"] + [f"{v:g}" for v in self.speed[:, j]])


def synthetic_cruising_polar() -> PolarTable:
    """Placeholder polar for a generic 40-ft cruising monohull.

    Decision #12 (polar source: synthetic vs OpenCPN library) is still open;
    this table is a documented synthetic stand-in shaped like a typical
    cruiser: no-go below ~40 deg TWA, best speed at ~100-120 deg TWA,
    hull speed plateau around 7.5 kt.
    """
    tws = np.array([0.0, 4.0, 6.0, 8.0, 10.0, 13.0, 16.0, 20.0, 25.0, 30.0, 40.0])
    twa = np.array(
        [0.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0, 135.0, 150.0, 165.0, 180.0]
    )

    # Shape: speed rises with wind up to a hull-speed plateau, falls off in
    # survival conditions; angle profile peaks near a broad reach.
    angle_profile = np.array(
        [0.0, 0.0, 0.55, 0.75, 0.88, 0.96, 1.0, 1.0, 0.97, 0.92, 0.85, 0.78]
    )
    max_speed = np.array([0.0, 2.2, 3.4, 4.6, 5.6, 6.6, 7.3, 7.6, 7.5, 7.2, 6.6])
    speed = np.outer(max_speed, angle_profile)
    return PolarTable(tws=tws, twa=twa, speed=speed)
