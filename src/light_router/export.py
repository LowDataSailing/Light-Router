"""Route export: GPX (the sailing-world standard, opens in OpenCPN) and
GeoJSON (web viewers, QGIS).

GPX writing uses gpxpy (optional dependency group ``artifacts``); GeoJSON is
plain JSON. Both are lazy so the core install stays numpy-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .isochrone import Route


def _require_gpxpy():
    try:
        import gpxpy.gpx  # type: ignore[import-untyped]

        return gpxpy
    except ImportError as exc:  # pragma: no cover - exercised via importorskip
        raise ImportError(
            "GPX export requires the optional 'artifacts' dependency group: "
            "uv sync --group artifacts"
        ) from exc


def route_to_gpx(route: Route, name: str, start_time: datetime | None = None) -> str:
    """Serialize a route as a GPX 1.1 track.

    Waypoint timestamps are only emitted when ``start_time`` is given (route
    times are hours since the scenario start, so synthetic runs have no
    wall-clock time).
    """
    gpxpy = _require_gpxpy()
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "light-router"
    track = gpxpy.gpx.GPXTrack(name=name)
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    for i in range(route.n_waypoints):
        point_time = None
        if start_time is not None:
            point_time = start_time + timedelta(hours=float(route.time[i]))
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(
                latitude=float(route.lat[i]),
                longitude=float(route.lon[i]),
                time=point_time,
            )
        )
    return gpx.to_xml()


def route_to_geojson(route: Route, name: str) -> dict[str, object]:
    """Serialize a route as a GeoJSON Feature (LineString + per-point props)."""
    coordinates = [
        [round(float(lon), 6), round(float(lat), 6)]
        for lat, lon in zip(route.lat, route.lon)
    ]
    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "reached": bool(route.reached),
            "eta_hours": float(route.eta_hours),
            "distance_nm": float(route.distance_nm),
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "points": [
            {
                "time_h": float(route.time[i]),
                "speed_kt": float(route.speed[i]),
                "heading_deg": float(route.heading[i]),
                "tws_kt": float(route.tws[i]),
                "twa_deg": float(route.twa[i]),
            }
            for i in range(route.n_waypoints)
        ],
    }


def write_route_files(run_dir: Path, route: Route, name: str) -> None:
    """Write ``<name>.gpx`` and ``<name>.geojson`` into the run directory."""
    gpx_path = run_dir / f"{name}.gpx"
    gpx_path.write_text(route_to_gpx(route, name))
    geojson_path = run_dir / f"{name}.geojson"
    geojson_path.write_text(json.dumps(route_to_geojson(route, name), indent=2) + "\n")


def read_routes(run_dir: Path) -> dict[str, list[tuple[float, float]]]:
    """Parse every ``*.gpx`` in a run directory back into tracks.

    Returns {file stem: [(lat, lon), ...]}; used by the summarize command to
    re-render plots without re-running the router.
    """
    gpxpy = _require_gpxpy()
    tracks: dict[str, list[tuple[float, float]]] = {}
    for path in sorted(run_dir.glob("*.gpx")):
        gpx = gpxpy.parse(path.read_text())
        points: list[tuple[float, float]] = []
        for track in gpx.tracks:
            for segment in track.segments:
                points.extend((p.latitude, p.longitude) for p in segment.points)
        tracks[path.stem] = points
    return tracks
