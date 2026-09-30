"""Minimal client for the open InfoClimat/CHOM climatology API.

The portal (https://portail.chom.engineering, API https://climato.chom.engineering)
serves station observations and aggregates — NOT forecasts (verified 2026-09-27).
For Light-Router it is a source of observation ground truth (e.g. buoys
measuring waves / sea-surface temperature) for later Mode B evaluation.

API contract: open JSON REST, no key, RFC 9457 problem+json errors,
`n = 0` is a legitimate empty result.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE_URL = "https://climato.chom.engineering"


@dataclass(frozen=True)
class Station:
    ic_id: str
    name: str
    latitude: float
    longitude: float
    country: str
    parameters: tuple[str, ...] = ()


def _get(
    path: str,
    params: dict[str, str] | None = None,
    base: str = BASE_URL,
    timeout_s: int = 15,
) -> dict:
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_stations(query: str, base: str = BASE_URL) -> list[Station]:
    """Resolve a station by name or identifier (max 20 results)."""
    payload = _get("/stations", {"q": query}, base=base)
    return [_station_from(s) for s in payload.get("stations", [])]


def stations_measuring(parameter: str, base: str = BASE_URL) -> list[Station]:
    """Referential stations that measure a canonical parameter (e.g.
    'sea_surface_wave_significant_height' for wave buoys)."""
    payload = _get("/ref/stations", {"parametre": parameter}, base=base)
    return [_station_from_feature(f) for f in payload.get("features", [])]


def station_parameters(ic_id: str, base: str = BASE_URL) -> tuple[str, ...]:
    """Parameters measured by a station, with observation depth."""
    payload = _get("/ref/station-parametre", {"station": ic_id}, base=base)
    rows = payload.get("mesures", payload if isinstance(payload, list) else [])
    return tuple(str(row.get("parametre", "")) for row in rows)


def _station_from(entry: dict) -> Station:
    return Station(
        ic_id=str(entry.get("ic_id", "")),
        name=str(entry.get("libelle", "")),
        latitude=float(entry.get("latitude", float("nan"))),
        longitude=float(entry.get("longitude", float("nan"))),
        country=str(entry.get("pays", "")),
        parameters=tuple(entry.get("parametres_mesures", ())),
    )


def _station_from_feature(feature: dict) -> Station:
    """Map a GeoJSON feature from /ref/stations to a Station."""
    props = feature.get("properties", {})
    lon, lat = feature.get("geometry", {}).get("coordinates", (None, None))
    entry = dict(props)
    entry["latitude"] = lat if lat is not None else float("nan")
    entry["longitude"] = lon if lon is not None else float("nan")
    return _station_from(entry)
