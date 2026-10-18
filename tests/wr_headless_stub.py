#!/usr/bin/env python3
"""Stub OpenCPN binary pinning the WR_HEADLESS_* JSON contract (issue #22).

Mimics the headless scenario runner of the pob220 weather_routing_pi fork
(branch routing-engine-refactor, docs/headless_scenarios.md): reads
WR_HEADLESS_SCENARIO and WR_HEADLESS_GRIB_FILE, validates the scenario
fields the adapter must produce, and writes the result JSON to
WR_HEADLESS_OUTPUT. The "route" is a plausible straight-line approximation
(great-circle distance at STUB_SPEED_KT), not a real isochrone solution —
this stub pins the process contract, not routing quality.

Set WR_STUB_RESULT_MODE=failed to make the stub emit a failure result, the
way the real runner reports "no_completed_routes".
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta

STUB_SPEED_KT = 6.5
"""Constant boat speed of the stub's straight-line approximation (kt)."""

EARTH_RADIUS_NM = 3440.065
"""Mean Earth radius (nm) — matches the library's great-circle helper."""

REQUIRED_SCENARIO_FIELDS = {
    "schemaVersion",
    "name",
    "start.lat",
    "start.lon",
    "end.lat",
    "end.lon",
    "startTime",
    "route.boatFile",
    "route.timeStepSeconds",
    "route.headingFromDegrees",
    "route.headingToDegrees",
    "route.headingStepDegrees",
    "route.maxTrueWindKnots",
    "route.maxApparentWindKnots",
    "route.routingEffortPercent",
    "safety.mode",
    "safety.enforce",
    "safety.landMarginNm",
    "safety.minimumDepthM",
}
"""Scenario fields the adapter must produce (the consumer-side contract)."""


def fail(message: str) -> None:
    """Exit loudly on a contract violation, so tests catch drift."""
    print(f"wr_headless_stub: {message}", file=sys.stderr)
    raise SystemExit(2)


def great_circle_distance_nm(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Haversine distance (nm) — self-contained, no repo imports."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_NM * math.asin(math.sqrt(min(1.0, a)))


def check_scenario(scenario: dict) -> None:
    """Validate the scenario against the contract, or exit loudly."""
    for field in sorted(REQUIRED_SCENARIO_FIELDS):
        value: object = scenario
        for part in field.split("."):
            if not isinstance(value, dict) or part not in value:
                fail(f"scenario is missing required field {field!r}")
            value = value[part]


def main() -> None:
    scenario_path = os.environ.get("WR_HEADLESS_SCENARIO")
    output_path = os.environ.get("WR_HEADLESS_OUTPUT")
    grib_path = os.environ.get("WR_HEADLESS_GRIB_FILE")
    if not scenario_path or not output_path:
        fail("WR_HEADLESS_SCENARIO and WR_HEADLESS_OUTPUT must be set")
    if not grib_path or not os.path.exists(grib_path):
        fail("WR_HEADLESS_GRIB_FILE must be set and exist")

    with open(scenario_path) as fh:
        scenario = json.load(fh)
    check_scenario(scenario)

    start = (scenario["start"]["lat"], scenario["start"]["lon"])
    end = (scenario["end"]["lat"], scenario["end"]["lon"])
    departure = datetime.fromisoformat(scenario["startTime"].replace("Z", "+00:00"))

    if os.environ.get("WR_STUB_RESULT_MODE") == "failed":
        payload = {
            "schemaVersion": 1,
            "scenario": scenario["name"],
            "status": "failed",
            "failureReason": "no_completed_routes",
            "candidates": [
                {
                    "departure": scenario["startTime"],
                    "state": "failed",
                    "finalSafety": "fail",
                    "failureReason": "No reachable route points",
                    "offsetMinutes": 0,
                }
            ],
            "diagnostics": {},
        }
    else:
        distance_nm = great_circle_distance_nm(*start, *end)
        elapsed_s = distance_nm / STUB_SPEED_KT * 3600.0
        payload = {
            "schemaVersion": 1,
            "scenario": scenario["name"],
            "status": "complete",
            "candidates": [
                {
                    "departure": scenario["startTime"],
                    "state": "complete",
                    "eta": (departure + timedelta(seconds=elapsed_s)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "elapsed": round(elapsed_s),
                    "distanceNm": round(distance_nm, 2),
                    "finalSafety": "pass",
                    "offsetMinutes": 0,
                    "reverseRecoveryUsed": False,
                    "reverseConnectionFound": False,
                    "reverseFinalValidationPass": False,
                }
            ],
            "diagnostics": {},
        }

    with open(output_path, "w") as fh:
        json.dump(payload, fh, indent=2)


if __name__ == "__main__":
    main()
