"""GFS AWS-archive downloader: index parsing, byte ranges, caching."""

from __future__ import annotations


import pytest

from light_router.weather_data.gfs_archive import (
    GribIndexEntry,
    download_gfs_archive_wind,
    gfs_archive_urls,
    message_byte_range,
    parse_grib_index,
)

IDX_TEXT = "\n".join(
    [
        "1:0:d=2025091500:PRMSL:mean sea level:anl:",
        "585:409369204:d=2025091500:UGRD:10 m above ground:anl:",
        "586:410342447:d=2025091500:VGRD:10 m above ground:anl:",
        "587:411315690:d=2025091500:FRICV:10 m above ground:anl:",
        "garbage line without colons",
    ]
)


def test_gfs_archive_urls():
    grib_url, idx_url = gfs_archive_urls("20250915", "00", 12)
    assert grib_url == (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20250915/00/atmos/"
        "gfs.t00z.pgrb2.0p25.f012"
    )
    assert idx_url == grib_url + ".idx"


def test_parse_grib_index():
    entries = parse_grib_index(IDX_TEXT)
    assert len(entries) == 4
    assert entries[1] == GribIndexEntry(
        message=585, byte_start=409369204, variable="UGRD", level="10 m above ground"
    )


def test_message_byte_range():
    entries = parse_grib_index(IDX_TEXT)
    start, end = message_byte_range(entries, entries[1])
    assert (start, end) == (409369204, 410342447)


def test_message_byte_range_last_entry_raises():
    entries = parse_grib_index(IDX_TEXT)
    with pytest.raises(ValueError, match="last entry"):
        message_byte_range(entries, entries[-1])


def test_download_writes_wind_messages(tmp_path, monkeypatch):
    from light_router.weather_data import gfs_archive

    fetched: list[tuple[str, int, int]] = []

    def fake_fetch_text(url, timeout_s):
        return IDX_TEXT

    def fake_fetch_range(url, start, end, timeout_s):
        fetched.append((url, start, end))
        return b"GRIB" + str(start).encode()

    monkeypatch.setattr(gfs_archive, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(gfs_archive, "fetch_range", fake_fetch_range)

    paths = download_gfs_archive_wind("20250915", "00", [0, 3], tmp_path)
    assert [p.name for p in paths] == [
        "gfs_2025091500_f000.grib2",
        "gfs_2025091500_f003.grib2",
    ]
    for path in paths:
        content = path.read_bytes()
        assert content.startswith(b"GRIB")
        assert len(content) == 26  # two 13-byte fake messages

    # exactly the two wind messages per file, at their index offsets
    assert len(fetched) == 4
    assert fetched[0] == (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20250915/00/atmos/"
        "gfs.t00z.pgrb2.0p25.f000",
        409369204,
        410342447,
    )

    # second call hits the cache: no new fetches
    download_gfs_archive_wind("20250915", "00", [0, 3], tmp_path)
    assert len(fetched) == 4


def test_download_missing_variable_raises(tmp_path, monkeypatch):
    from light_router.weather_data import gfs_archive

    monkeypatch.setattr(
        gfs_archive, "fetch_text", lambda url, timeout_s: IDX_TEXT.splitlines()[0]
    )
    with pytest.raises(ValueError, match="matching messages"):
        download_gfs_archive_wind("20250915", "00", [0], tmp_path)
