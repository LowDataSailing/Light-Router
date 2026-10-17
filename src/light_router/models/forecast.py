"""Forecast cycles: the runs a router may receive during a passage.

``ForecastCycle`` is weather-domain (a run and its forecast), so it lives in
the library next to the data clients that produce it and the packs that
store it. The simulation-side records (what the router believed, what
actually happened) live in ``experiments/models/passage.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import xarray as xr


@dataclass
class ForecastCycle:
    """One GFS run available to the router during the passage."""

    init_hour: float
    """Run initialization, in absolute hours since passage start."""

    weather: xr.Dataset
    """The run's forecast as a CF Dataset, time = lead hours since its own
    initialization."""
