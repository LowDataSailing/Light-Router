"""GFS historical archive access (NOAA Open Data on AWS S3).

NOMADS only serves roughly the last 14 days of GFS runs, so historical
scenarios (Compatibility rule 4: real archived forecasts) come from the
``noaa-gfs-bdp-pds`` bucket. Full 0.25-degree files are ~1 GB per forecast
hour, but each ships a wgrib2 index (``.idx``) listing the byte offset of
every GRIB message — so only the UGRD/VGRD 10 m messages are fetched with
HTTP range requests (~2 MB per hour instead of ~1 GB). This is the same
technique the Herbie library uses.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

ARCHIVE_BASE_URL = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"


@dataclass(frozen=True)
class GribIndexEntry:
    """One wgrib2 index line: a GRIB message's number and byte offset."""

    message: int
    byte_start: int
    variable: str
    level: str


def gfs_archive_urls(
    rundate: str, run_hour: str, forecast_hour: int
) -> tuple[str, str]:
    """(grib_url, index_url) of one forecast hour in the AWS archive.

    rundate: YYYYMMDD; run_hour: "00"|"06"|"12"|"18"; forecast_hour: 0..384.
    """
    file = f"gfs.t{run_hour}z.pgrb2.0p25.f{forecast_hour:03d}"
    base = f"{ARCHIVE_BASE_URL}/gfs.{rundate}/{run_hour}/atmos"
    return f"{base}/{file}", f"{base}/{file}.idx"


def parse_grib_index(text: str) -> list[GribIndexEntry]:
    """Parse a wgrib2 ``.idx`` into entries (message, byte start, variable, level).

    Line format: ``585:409369204:d=2025091500:UGRD:10 m above ground:anl:``
    """
    entries: list[GribIndexEntry] = []
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) < 5:
            continue
        try:
            message, byte_start = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        entries.append(
            GribIndexEntry(
                message=message,
                byte_start=byte_start,
                variable=parts[3],
                level=parts[4],
            )
        )
    return entries


def message_byte_range(
    entries: list[GribIndexEntry], entry: GribIndexEntry
) -> tuple[int, int]:
    """``[start, end)`` byte range of one message: its start to the next message's.

    The wind messages are never last in a GFS pgrb2 file, so the next
    message's offset always bounds them.
    """
    index = entries.index(entry)
    if index + 1 >= len(entries):
        raise ValueError(
            f"cannot determine the end of GRIB message {entry.message} "
            "from the index (it is the last entry)"
        )
    return entry.byte_start, entries[index + 1].byte_start


def _fetch_text(url: str, timeout_s: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return response.read().decode()


def _fetch_range(url: str, start: int, end: int, timeout_s: int) -> bytes:
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end - 1}"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read()


def download_gfs_archive_wind(
    rundate: str,
    run_hour: str,
    forecast_hours: list[int],
    cache_dir: Path,
    variables: tuple[str, ...] = ("UGRD", "VGRD"),
    level: str = "10 m above ground",
    timeout_s: int = 120,
) -> list[Path]:
    """Download archived GFS wind messages into cache_dir (skips existing).

    Each forecast hour yields one small GRIB2 file containing just the
    requested messages, extracted from the ~1 GB archive file with HTTP
    range requests. Returns the local paths, ordered by forecast hour.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for fh in sorted(forecast_hours):
        dest = cache_dir / f"gfs_{rundate}{run_hour}_f{fh:03d}.grib2"
        if not dest.exists():
            grib_url, idx_url = gfs_archive_urls(rundate, run_hour, fh)
            entries = parse_grib_index(_fetch_text(idx_url, timeout_s))
            wanted = [
                e for e in entries if e.variable in variables and e.level == level
            ]
            if len(wanted) != len(variables):
                raise ValueError(
                    f"archive index for f{fh:03d} has {len(wanted)} matching "
                    f"messages, expected {variables} at {level!r}"
                )
            with open(dest, "wb") as out:
                for entry in wanted:
                    start, end = message_byte_range(entries, entry)
                    out.write(_fetch_range(grib_url, start, end, timeout_s))
        paths.append(dest)
    return paths
