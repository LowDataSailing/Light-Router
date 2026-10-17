"""Synthetic polar fixture: a documented stand-in boat, not a research input.

Decision #12 (polar source: synthetic vs OpenCPN library) is still open; this
table is the experiment-domain placeholder used by the experiments and the
test suite until a real polar lands. It lives in ``experiments/`` — not in
the library — because it is experiment data, not router code.
"""

from __future__ import annotations

import numpy as np

from light_router.models.vessel import PolarTable


def synthetic_cruising_polar() -> PolarTable:
    """Placeholder polar for a generic 40-ft cruising monohull.

    Shaped like a typical cruiser: no-go below ~40 deg TWA, best speed at
    ~100-120 deg TWA, hull speed plateau around 7.5 kt.
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
