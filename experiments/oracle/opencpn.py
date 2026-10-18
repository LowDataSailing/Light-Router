"""OpenCPN WeatherRouting oracle adapter: the pinned headless subprocess.

Drives the pob220 fork of the OpenCPN weather-routing plugin through its
headless JSON runner (branch ``routing-engine-refactor``, document
``docs/headless_scenarios.md`` in the fork): the adapter writes a scenario
JSON, an OpenCPN-style polar CSV and a wind file, runs the pinned OpenCPN
binary with the ``WR_HEADLESS_*`` environment variables, and parses the
runner's JSON result into a
:class:`~light_router.models.route.Route`.

Building OpenCPN is out of scope for this adapter (it happens later on a
capable machine); when the configured binary is absent the adapter raises an
informative error naming the exact pin. The tests exercise the full JSON
contract with a stub binary (``tests/wr_headless_stub.py``) that mimics the
``WR_HEADLESS_*`` interface.

GRIB gap (honest limitation): the pinned binary consumes GRIB2 through
``WR_HEADLESS_GRIB_FILE``, but this repo's GRIB support is read-only (cfgrib)
and no GRIB2 encoder is a current dependency. Until one lands, the adapter
writes the wind field as JSON (:func:`write_wind_field_json`) and passes it
through the same environment variable; the stub tests pin the
scenario/result contract, not the GRIB encoding. Swapping in a real GRIB2
writer is a one-function change behind that seam.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import xarray as xr

from light_router.dataset import grid_from_dataset
from light_router.models.route import Route, Waypoint
from light_router.models.vessel import PolarTable
from experiments.synthetic import SYNTHETIC_EPOCH

OPENCPN_ORACLE_REPO = "https://github.com/pob220/weather_routing_pi"
"""Repository of the pinned OpenCPN WeatherRouting oracle build."""

OPENCPN_ORACLE_BRANCH = "routing-engine-refactor"
"""Branch of the pinned oracle build (carries the headless JSON runner)."""

OPENCPN_ORACLE_COMMIT = "ae09f413188994e7f13906aa2f18d2666c0e77da"
"""Exact commit of the pinned oracle build."""

OPENCPN_ORACLE_PIN = (
    f"{OPENCPN_ORACLE_REPO}@{OPENCPN_ORACLE_BRANCH}@{OPENCPN_ORACLE_COMMIT}"
)
"""The full pin recorded in the adapter's ``name`` and error messages."""

WR_HEADLESS_SCENARIO_ENV = "WR_HEADLESS_SCENARIO"
"""Environment variable pointing the runner at the scenario JSON file."""

WR_HEADLESS_GRIB_FILE_ENV = "WR_HEADLESS_GRIB_FILE"
"""Environment variable pointing the runner at the weather input file."""

WR_HEADLESS_OUTPUT_ENV = "WR_HEADLESS_OUTPUT"
"""Environment variable pointing the runner at the result JSON file."""

SCENARIO_SCHEMA_VERSION = 1
"""Scenario/result schema version of the fork's headless runner."""

RESULT_STATUS_COMPLETE = "complete"
"""Runner status for a run that produced at least one completed route."""

CANDIDATE_STATE_COMPLETE = "complete"
"""Candidate state for a route that reached the destination."""


@dataclass
class OpenCPNConfig:
    """Tuning surface mirrored one-to-one into the headless scenario JSON."""

    time_step_seconds: int = 3600
    """Routing time step (s) — one isochrone level per step."""

    heading_from_deg: float = 0.0
    """First candidate heading (deg true)."""

    heading_to_deg: float = 360.0
    """Last candidate heading (deg true)."""

    heading_step_deg: float = 5.0
    """Heading increment (deg) between candidates."""

    max_true_wind_knots: float = 60.0
    """Maximum true wind the boat will accept (kt)."""

    max_apparent_wind_knots: float = 60.0
    """Maximum apparent wind the boat will accept (kt)."""

    routing_effort_percent: int = 100
    """Search-effort budget; the runner accepts 100, 150, 200 or 400."""

    safety_mode: str = "none"
    """Land/depth safety source: ``none``, ``gshhs`` or ``chart``."""

    safety_enforce: bool = False
    """Whether safety violations reject the route."""

    land_margin_nm: float = 0.0
    """Keep-out margin around land (nm)."""

    minimum_depth_m: float = 0.0
    """Minimum chart depth (m); only applied in ``chart`` safety mode."""

    def __post_init__(self) -> None:
        if self.time_step_seconds <= 0:
            raise ValueError("time_step_seconds must be positive")
        if self.heading_step_deg <= 0:
            raise ValueError("heading_step_deg must be positive")
        if self.routing_effort_percent not in (100, 150, 200, 400):
            raise ValueError("routing_effort_percent must be one of 100, 150, 200, 400")
        if self.safety_mode not in ("none", "gshhs", "chart"):
            raise ValueError(
                "safety_mode must be 'none', 'gshhs' or 'chart', "
                f"got {self.safety_mode!r}"
            )


def build_scenario(
    start: tuple[float, float],
    finish: tuple[float, float],
    start_datetime: datetime,
    boat_file: Path,
    config: OpenCPNConfig,
) -> dict[str, Any]:
    """Build the headless scenario JSON (a plain dict) for one passage.

    ``start_datetime`` is the departure instant (UTC). The layout mirrors
    the fork's documented schema: ``start``/``end`` positions, ``startTime``,
    a ``route`` block (polar, time step, heading range, wind constraints,
    effort) and a ``safety`` block.
    """
    return {
        "schemaVersion": SCENARIO_SCHEMA_VERSION,
        "name": f"Light-Router oracle validation {start} -> {finish}",
        "start": {"name": "start", "lat": start[0], "lon": start[1]},
        "end": {"name": "finish", "lat": finish[0], "lon": finish[1]},
        "startTime": start_datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {"useCurrents": False, "useGrib": True},
        "route": {
            "boatFile": str(boat_file),
            "timeStepSeconds": config.time_step_seconds,
            "headingFromDegrees": config.heading_from_deg,
            "headingToDegrees": config.heading_to_deg,
            "headingStepDegrees": config.heading_step_deg,
            "maxTrueWindKnots": config.max_true_wind_knots,
            "maxApparentWindKnots": config.max_apparent_wind_knots,
            "routingEffortPercent": config.routing_effort_percent,
        },
        "safety": {
            "mode": config.safety_mode,
            "enforce": config.safety_enforce,
            "landMarginNm": config.land_margin_nm,
            "minimumDepthM": config.minimum_depth_m,
            "persistentCertifiedCacheEnabled": False,
        },
    }


def parse_result(
    payload: dict[str, Any],
    start: tuple[float, float],
    finish: tuple[float, float],
    start_time: float,
) -> Route:
    """Parse the runner's result JSON into a Route.

    The headless runner's first milestone exposes no track geometry — only
    per-candidate ``eta``/``elapsed``/``distanceNm`` — so a reached route
    carries exactly the two known waypoints (start and finish); the derived
    distance is their great-circle, not the runner's reported sailed
    ``distanceNm`` (parsed only to pin the contract). Track comparisons
    against this oracle are degenerate (a straight line) and the validation
    report records the waypoint count so downstream readers can tell. A
    failed run produces the partial route containing only the start point.
    """
    status = payload.get("status")
    candidates = payload.get("candidates", [])
    completed = [c for c in candidates if c.get("state") == CANDIDATE_STATE_COMPLETE]
    if status != RESULT_STATUS_COMPLETE or not completed:
        return _partial_route(start, start_time)

    for candidate in completed:
        for key in ("elapsed", "distanceNm"):
            if key not in candidate:
                raise ValueError(
                    f"OpenCPN result candidate is missing {key!r}; the "
                    f"pinned runner contract ({OPENCPN_ORACLE_PIN}) "
                    "guarantees it for completed candidates"
                )
    best = min(completed, key=lambda c: float(c["elapsed"]))
    float(best["distanceNm"])  # contract-validated, not representable below
    eta_hours = start_time + float(best["elapsed"]) / 3600.0
    return Route(
        waypoints=[
            Waypoint(lat=start[0], lon=start[1], time=start_time),
            Waypoint(lat=finish[0], lon=finish[1], time=eta_hours),
        ],
        reached=True,
    )


def _partial_route(start: tuple[float, float], start_time: float) -> Route:
    """Route for a failed oracle run: the start point, nothing else."""
    return Route(
        waypoints=[Waypoint(lat=start[0], lon=start[1], time=start_time)],
        reached=False,
    )


def write_wind_field_json(weather: xr.Dataset, path: Path) -> None:
    """Write the wind field as JSON for the oracle's weather input.

    GRIB gap: the pinned binary expects a GRIB2 file at
    ``WR_HEADLESS_GRIB_FILE``, but writing GRIB2 needs an encoder that is
    not a dependency of this repo (cfgrib only reads). Until a GRIB2 writer
    lands, the adapter writes the u10/v10 field (m/s, on the dataset's
    lat/lon/time axes, time in hours since initialization) as JSON and
    passes it through the same variable; the stub binary pins the contract.
    """
    grid = grid_from_dataset(weather)
    payload = {
        "lats": [float(v) for v in grid.lats],
        "lons": [float(v) for v in grid.lons],
        "times_hours": [float(v) for v in grid.times],
        "u10_ms": grid.data["u10"].tolist(),
        "v10_ms": grid.data["v10"].tolist(),
    }
    path.write_text(json.dumps(payload))


@dataclass
class OpenCPNRouter:
    """Router adapter over the pinned OpenCPN headless binary.

    Satisfies the :class:`~light_router.routing.protocol.Router` protocol
    structurally (no inheritance from library code): the setup (binary,
    polar, scenario tuning) travels in the attributes and
    :meth:`for_weather` binds it to a weather dataset. ``route()`` writes
    the scenario, polar and wind files into ``workdir`` (a fresh temporary
    directory per call when None), runs the binary, and parses the result.
    """

    binary: Path
    """Path of the pinned OpenCPN executable (the headless entry point)."""

    weather: xr.Dataset | None = field(default=None, kw_only=True)
    """Canonical CF weather dataset for the passage (Compatibility rule 1);
    bound by :meth:`for_weather`, None until then."""

    polar: PolarTable
    """Boat polar, written as an OpenCPN-style CSV for ``route.boatFile``."""

    config: OpenCPNConfig = field(default_factory=OpenCPNConfig)
    """Scenario tuning mirrored into the scenario JSON."""

    start_datetime: datetime | None = None
    """Calendar time of weather hour 0 (UTC); None means the synthetic
    epoch (``experiments.synthetic.SYNTHETIC_EPOCH``)."""

    workdir: Path | None = None
    """Directory for the scenario/polar/wind/result files; None means a
    fresh temporary directory per ``route()`` call."""

    cwd: Path | None = None
    """Working directory for the subprocess; the fork's runner resolves
    relative plugin paths from the OpenCPN source tree, so point this at
    it when running the real binary."""

    timeout_seconds: float = 600.0
    """Subprocess timeout (s); a real isochrone run can take minutes."""

    name: ClassVar[str] = f"opencpn-weather-routing@{OPENCPN_ORACLE_PIN}"
    """Adapter identity: the exact oracle build this instance drives."""

    def for_weather(self, weather: xr.Dataset) -> OpenCPNRouter:
        """Bind this oracle setup to a weather dataset.

        The binding is cheap (the dataset is written to disk at
        :meth:`route` time, once per passage), so it is a plain
        :func:`dataclasses.replace`.
        """
        return replace(self, weather=weather)

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route:
        """Run the pinned binary for one passage and parse its result.

        ``start_time`` is the departure in hours since weather hour 0; the
        scenario's ``startTime`` is the anchor datetime plus it.
        """
        if self.weather is None:
            raise RuntimeError(
                "OpenCPN oracle router is not bound to weather yet; "
                "call for_weather(weather) first"
            )
        if not self._binary_available():
            raise RuntimeError(self._missing_binary_message())

        workdir = (
            self.workdir
            if self.workdir is not None
            else Path(tempfile.mkdtemp(prefix="lr-opencpn-oracle-"))
        )
        workdir.mkdir(parents=True, exist_ok=True)
        boat_file = workdir / "polar.csv"
        self.polar.to_polar_csv(boat_file)
        wind_file = workdir / "wind_field.json"
        write_wind_field_json(self.weather, wind_file)
        scenario_file = workdir / "scenario.json"
        output_file = workdir / "result.json"

        epoch = (
            self.start_datetime if self.start_datetime is not None else SYNTHETIC_EPOCH
        )
        departure = epoch + timedelta(hours=start_time)
        scenario = build_scenario(start, finish, departure, boat_file, self.config)
        scenario_file.write_text(json.dumps(scenario, indent=2))

        env = {
            **os.environ,
            WR_HEADLESS_SCENARIO_ENV: str(scenario_file),
            WR_HEADLESS_GRIB_FILE_ENV: str(wind_file),
            WR_HEADLESS_OUTPUT_ENV: str(output_file),
        }
        proc = subprocess.run(
            [str(self.binary)],
            cwd=self.cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"OpenCPN oracle binary {self.binary} exited with code "
                f"{proc.returncode}: {proc.stderr.strip()[-500:]}"
            )
        if not output_file.exists():
            raise RuntimeError(
                "OpenCPN oracle binary did not write the result file at "
                f"{output_file}; the plugin may not have loaded (see the "
                "fork's docs/headless_scenarios.md, 'Verifying Plugin Load')"
            )
        payload = json.loads(output_file.read_text())
        return parse_result(payload, start, finish, start_time)

    def _binary_available(self) -> bool:
        return self.binary.exists() and os.access(self.binary, os.X_OK)

    def _missing_binary_message(self) -> str:
        return (
            f"OpenCPN oracle binary not found or not executable: {self.binary}. "
            f"This adapter drives the pinned build {OPENCPN_ORACLE_PIN} "
            "(headless JSON runner, docs/headless_scenarios.md in the fork). "
            "Building OpenCPN is out of scope for the adapter: build that "
            "exact commit on a capable machine and point the adapter at the "
            "resulting executable."
        )
