"""Oracle reference routers: the industry adapters over the Router seam.

Two adapters, one seam (Compatibility rule 2): ``opencpn`` drives the
pinned OpenCPN WeatherRouting build through its headless JSON runner as a
subprocess, ``libweatherrouting`` wraps the GPLv3 PyPI package in-process
as the live secondary cross-check. ``validate`` is the harness (and the
script entry point, ``uv run python -m experiments.oracle.validate``) that
quantifies the in-repo isochrone surrogate's bias against whichever oracle
is available. All three live in ``experiments/``: they exist to validate
the surrogate, not to run on a boat.
"""

from __future__ import annotations

from experiments.oracle.libweatherrouting import (
    LibWeatherRoutingConfig,
    LibWeatherRoutingRouter,
)
from experiments.oracle.opencpn import (
    OPENCPN_ORACLE_PIN,
    OpenCPNConfig,
    OpenCPNRouter,
)

__all__ = [
    "LibWeatherRoutingConfig",
    "LibWeatherRoutingRouter",
    "OPENCPN_ORACLE_PIN",
    "OpenCPNConfig",
    "OpenCPNRouter",
]
