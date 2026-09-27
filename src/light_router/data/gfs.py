"""GFS data acquisition via the NOAA NOMADS grib filter.

Builds filtered download URLs (U10/V10 at 10 m above ground, subregion,
selected forecast hours) and downloads them to a cache directory.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

NOMADS_FILTER_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs.pl"


def gfs_filter_url(
    rundate: str,
    run_hour: str,
    forecast_hour: int,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
) -> str:
    """URL of a filtered GFS GRIB2 file (wind at 10 m, subregion).

    rundate: YYYYMMDD; run_hour: "00"|"06"|"12"|"18"; forecast_hour: 0..384.
    """
    file = f"gfs.t{run_hour}z.pgrb2.0p25.f{forecast_hour:03d}"
    params = {
        "dir": f"/gfs.{rundate}/{run_hour}",
        "file": file,
        "lev_10_m_above_ground": "on",
        "var_UGRD": "on",
        "var_VGRD": "on",
        "leftlon": f"{lon_min:.2f}",
        "rightlon": f"{lon_max:.2f}",
        "toplat": f"{lat_max:.2f}",
        "bottomlat": f"{lat_min:.2f}",
    }
    return f"{NOMADS_FILTER_URL}?{urllib.parse.urlencode(params)}"


def download_gfs_wind(
    rundate: str,
    run_hour: str,
    forecast_hours: list[int],
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    cache_dir: Path,
    timeout_s: int = 120,
) -> list[Path]:
    """Download filtered GFS wind GRIB2 files into cache_dir (skips existing).

    Returns the local paths, ordered by forecast hour.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for fh in sorted(forecast_hours):
        name = f"gfs_{rundate}{run_hour}_f{fh:03d}.grib2"
        dest = cache_dir / name
        if not dest.exists():
            url = gfs_filter_url(
                rundate, run_hour, fh, lon_min, lon_max, lat_min, lat_max
            )
            tmp = dest.with_suffix(".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(dest)
        paths.append(dest)
    return paths
