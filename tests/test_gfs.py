from light_router.weather_data.gfs import download_gfs_wind, gfs_filter_url


def test_url_contains_region_and_variables():
    url = gfs_filter_url("20260926", "00", 12, -27.0, -12.0, 12.0, 32.0)
    assert "filter_gfs.pl" in url
    assert "dir=%2Fgfs.20260926%2F00" in url
    assert "var_UGRD=on" in url and "var_VGRD=on" in url
    assert "lev_10_m_above_ground=on" in url
    assert "leftlon=-27.00" in url and "toplat=32.00" in url
    assert "f012" in url


def test_download_skips_existing(tmp_path, monkeypatch):
    from light_router.weather_data import gfs

    cached = tmp_path / "gfs_2026092600_f000.grib2"
    cached.write_bytes(b"fake grib")
    called = []
    monkeypatch.setattr(gfs, "fetch_bytes", lambda *a, **k: called.append(a))
    paths = download_gfs_wind(
        "20260926", "00", [0], -27.0, -12.0, 12.0, 32.0, cache_dir=tmp_path
    )
    assert paths == [cached]
    assert called == []  # nothing downloaded
