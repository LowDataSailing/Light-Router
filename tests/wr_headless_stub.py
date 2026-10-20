#!/usr/bin/env python3
"""Stub OpenCPN binary pinning the WR_HEADLESS_* JSON contract (issue #22).

Mimics the headless scenario runner of the pob220 weather_routing_pi fork
(branch routing-engine-refactor, docs/headless_scenarios.md): reads
WR_HEADLESS_SCENARIO and WR_HEADLESS_GRIB_FILE, validates the scenario
fields the adapter must produce, and writes the result JSON to
WR_HEADLESS_OUTPUT.

The "route" is not a routing solution — it is the boat sailing the direct
great circle at the speed the actual weather and polar allow, sampled
from the wind file (JSON or GRIB2) and the polar named by
``route.boatFile``. That makes it an honest lower bound: the same
geometry a real router could beat by dodging weather, with a travel time
that moves with the wind. Dead calm (or a wind horizon that runs out)
means the boat does not arrive: the stub reports the runner's
``no_completed_routes`` failure, and the adapter parses that as the
partial route — the boat not moving.

Set WR_STUB_RESULT_MODE=failed to force the failure result, the way the
real runner reports "no_completed_routes".
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta

EARTH_RADIUS_NM = 3440.065
"""Mean Earth radius (nm) — matches the library's great-circle helper."""

MIN_SAIL_KT = 0.1
"""Below this polar speed the boat makes no way (dead calm / head wind)."""

STEP_HOURS = 1.0
"""March step along the great circle (h) — the stub's time resolution."""

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


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing (deg true) from point 1 toward point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        dlam
    )
    return math.degrees(math.atan2(y, x)) % 360.0


def destination(lat: float, lon: float, bearing_deg: float, dist_nm: float):
    """Point reached sailing ``dist_nm`` along ``bearing_deg`` from (lat, lon)."""
    d = dist_nm / EARTH_RADIUS_NM
    brg = math.radians(bearing_deg)
    phi, lam = math.radians(lat), math.radians(lon)
    phi2 = math.asin(
        math.sin(phi) * math.cos(d) + math.cos(phi) * math.sin(d) * math.cos(brg)
    )
    lam2 = lam + math.atan2(
        math.sin(brg) * math.sin(d) * math.cos(phi),
        math.cos(d) - math.sin(phi) * math.sin(phi2),
    )
    return math.degrees(phi2), math.degrees(lam2)


def check_scenario(scenario: dict) -> None:
    """Validate the scenario against the contract, or exit loudly."""
    for field_path in sorted(REQUIRED_SCENARIO_FIELDS):
        value: object = scenario
        for part in field_path.split("."):
            if not isinstance(value, dict) or part not in value:
                fail(f"scenario is missing required field {field_path!r}")
            value = value[part]


# --- weather input: JSON (dependency-free) or GRIB2 (ecCodes) ---------------


def load_wind(path: str) -> dict:
    """Load the wind field: {lats, lons, times_hours, u10_ms, v10_ms}.

    ``u10_ms``/``v10_ms`` are [time][lat][lon] nested lists, m/s, axes
    ascending. GRIB2 files (the adapter writes them when ecCodes is
    installed) are decoded with the same bindings; JSON is the fallback
    form environments without the grib group produce.
    """
    with open(path, "rb") as fh:
        if fh.read(4) == b"GRIB":
            return load_wind_grib(path)
    with open(path) as fh:
        return json.load(fh)


def load_wind_grib(path: str) -> dict:
    """Decode the adapter's GRIB2 wind file (u10/v10, regular ll, hour steps)."""
    try:
        import eccodes
    except ImportError:
        fail("wind file is GRIB2 but the ecCodes bindings are not importable")
    lats = lons = times = None
    fields: dict = {}
    with open(path, "rb") as fh:
        while True:
            handle = eccodes.codes_new_from_file(
                fh, product_kind=eccodes.CODES_PRODUCT_GRIB
            )
            if handle is None:
                break
            try:
                short = eccodes.codes_get(handle, "shortName")
                if short not in ("10u", "10v"):
                    continue
                if lats is None:
                    ni = eccodes.codes_get(handle, "Ni")
                    nj = eccodes.codes_get(handle, "Nj")
                    lat0 = eccodes.codes_get(
                        handle, "latitudeOfFirstGridPointInDegrees"
                    )
                    lon0 = eccodes.codes_get(
                        handle, "longitudeOfFirstGridPointInDegrees"
                    )
                    dlat = eccodes.codes_get(handle, "jDirectionIncrementInDegrees")
                    dlon = eccodes.codes_get(handle, "iDirectionIncrementInDegrees")
                    asc = bool(eccodes.codes_get(handle, "jScansPositively"))
                    lats = [lat0 + (r if asc else nj - 1 - r) * dlat for r in range(nj)]
                    lons = [lon0 + c * dlon for c in range(ni)]
                    times = []
                step = int(eccodes.codes_get(handle, "forecastTime"))
                values = list(eccodes.codes_get_values(handle))
                rows = [values[r * ni : (r + 1) * ni] for r in range(nj)]
                if not asc:
                    rows = rows[::-1]
                fields.setdefault(step, {})[short] = rows
            finally:
                eccodes.codes_release(handle)
    if not fields:
        fail("GRIB2 wind file carries no 10u/10v messages")
    steps = sorted(fields)
    if lats is None or lons is None or times is None:
        fail("unreachable: geometry unset with data present")
    return {
        "lats": lats,
        "lons": lons,
        "times_hours": [float(s) for s in steps],
        "u10_ms": [fields[s]["10u"] for s in steps],
        "v10_ms": [fields[s]["10v"] for s in steps],
    }


def load_polar(boat_path: str) -> dict:
    """Load the adapter's boat XML -> the referenced .pol polar.

    ``route.boatFile`` is a boat XML referencing a semicolon .pol file
    (``twa/tws`` header, one row per TWA, speeds in kt); returns
    {tws, twa, speed[twa][tws]}.
    """
    import xml.etree.ElementTree as ET

    root = ET.parse(boat_path).getroot()
    polar_el = root.find("Polar")
    if polar_el is None or polar_el.get("FileName") is None:
        fail(f"boat file {boat_path} carries no Polar element")
    with open(polar_el.get("FileName")) as fh:
        rows = [line.rstrip("\n").split(";") for line in fh if line.strip()]
    if not rows or rows[0][0] != "twa/tws":
        fail("polar file is not the expected twa/tws .pol format")
    tws = [float(v) for v in rows[0][1:]]
    twa, speed = [], []
    for row in rows[1:]:
        twa.append(float(row[0]))
        speed.append([float(v) if v else 0.0 for v in row[1:]])
    return {"tws": tws, "twa": twa, "speed": speed}


def _interp(axis: list, x: float) -> tuple:
    """Bracketing indices on a sorted axis and the weight of the upper one."""
    if x <= axis[0]:
        return 0, 0, 0.0
    if x >= axis[-1]:
        return len(axis) - 1, len(axis) - 1, 0.0
    i = 1
    while axis[i] < x:
        i += 1
    lo, hi = i - 1, i
    w = (x - axis[lo]) / (axis[hi] - axis[lo])
    return lo, hi, w


def wind_at(wind: dict, hours: float, lat: float, lon: float):
    """Bilinear wind (speed kt, from-direction deg) at a point and time."""
    t_ax = wind["times_hours"]
    if hours < t_ax[0] or hours > t_ax[-1]:
        return None  # no data is no data: outside the forecast horizon
    lat_c = min(max(lat, wind["lats"][0]), wind["lats"][-1])
    lon_c = min(max(lon, wind["lons"][0]), wind["lons"][-1])
    r0, r1, rw = _interp(wind["lats"], lat_c)
    c0, c1, cw = _interp(wind["lons"], lon_c)
    t0, t1, tw = _interp(t_ax, hours)

    def uv(step: int) -> tuple:
        def grid(field: str) -> float:
            g = wind[field][step]
            return (
                g[r0][c0] * (1 - rw) * (1 - cw)
                + g[r0][c1] * (1 - rw) * cw
                + g[r1][c0] * rw * (1 - cw)
                + g[r1][c1] * rw * cw
            )

        return grid("u10_ms"), grid("v10_ms")

    u, v = uv(t0)
    if t1 != t0:
        u1, v1 = uv(t1)
        u, v = u * (1 - tw) + u1 * tw, v * (1 - tw) + v1 * tw
    speed_ms = math.hypot(u, v)
    speed_kt = speed_ms * 1.94384
    direction = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return speed_kt, direction


def polar_speed(polar: dict, tws_kt: float, twa_deg: float) -> float:
    """Boat speed (kt) from the polar, bilinear in (TWS, folded TWA)."""
    twa = abs(twa_deg) % 360.0
    if twa > 180.0:
        twa = 360.0 - twa
    tws_ax, twa_ax = polar["tws"], polar["twa"]
    s0, s1, sw = _interp(tws_ax, tws_kt)
    a0, a1, aw = _interp(twa_ax, twa)
    speed = polar["speed"]

    def at(a: int, s: int) -> float:
        return speed[a][s]

    return (
        at(a0, s0) * (1 - aw) * (1 - sw)
        + at(a0, s1) * (1 - aw) * sw
        + at(a1, s0) * aw * (1 - sw)
        + at(a1, s1) * aw * sw
    )


def sail_the_line(start, finish, wind: dict, polar: dict):
    """Sail the direct great circle at the weather-allowed speed.

    The boat never leaves the line: when the polar can sail the line's
    course it advances, when it cannot (dead calm, dead upwind) it makes
    no way and time passes — the honest cost of refusing to tack. It
    arrives when the finish comes within one step's run, and fails
    (None) only when the forecast horizon runs out first: the boat not
    moving, like the real runner's no_completed_routes.
    """
    lat, lon = start
    sailed = 0.0
    hours = float(wind["times_hours"][0])
    horizon = float(wind["times_hours"][-1])
    while hours <= horizon:
        remaining = great_circle_distance_nm(lat, lon, finish[0], finish[1])
        bearing = initial_bearing_deg(lat, lon, finish[0], finish[1])
        sampled = wind_at(wind, hours, lat, lon)
        if sampled is None:
            return None  # no weather to even wait on: the honest failure
        tws_kt, wind_from = sampled
        twa = abs((bearing - wind_from) % 360.0)
        if twa > 180.0:
            twa = 360.0 - twa
        kt = polar_speed(polar, tws_kt, twa)
        if kt < MIN_SAIL_KT:
            kt = 0.0  # unsailable line: the boat waits, no way made
        leg = kt * STEP_HOURS
        if leg >= remaining:
            return (hours - float(wind["times_hours"][0]) + remaining / kt) * 3600.0, (
                sailed + remaining
            )
        if kt > 0.0:
            lat, lon = destination(lat, lon, bearing, leg)
            sailed += leg
        hours += STEP_HOURS
    return None


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
        wind = load_wind(grib_path)
        polar = load_polar(scenario["route"]["boatFile"])
        outcome = sail_the_line(start, end, wind, polar)
        if outcome is None:
            # the boat does not arrive on this weather: the honest
            # failure, like the real runner's "no_completed_routes"
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
            elapsed_s, distance_nm = outcome
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
