import json
from unittest.mock import patch

from light_router.weather_data import chom


def fake_response(payload):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(payload).encode()

    return FakeResponse()


def test_search_stations_parses_entries():
    payload = {
        "stations": [
            {
                "ic_id": "07486",
                "libelle": "Trappes (78)",
                "latitude": 48.77,
                "longitude": 2.01,
                "pays": "France",
                "parametres_mesures": ["air_temperature"],
            }
        ]
    }
    with patch.object(
        chom.urllib.request, "urlopen", return_value=fake_response(payload)
    ):
        stations = chom.search_stations("trappes")
    assert len(stations) == 1
    assert stations[0].ic_id == "07486"
    assert stations[0].parameters == ("air_temperature",)


def test_stations_measuring_parses_geojson():
    payload = {
        "features": [
            {
                "properties": {"ic_id": "62001", "libelle": "Bouée", "pays": "France"},
                "geometry": {"coordinates": [-5.0, 48.5]},
            }
        ]
    }
    with patch.object(
        chom.urllib.request, "urlopen", return_value=fake_response(payload)
    ):
        stations = chom.stations_measuring("sea_surface_wave_significant_height")
    assert stations[0].latitude == 48.5
    assert stations[0].longitude == -5.0


def test_station_parameters_extracts_names():
    payload = {
        "mesures": [
            {"parametre": "air_temperature", "n_obs": 100},
            {"parametre": "wind_speed", "n_obs": 50},
        ]
    }
    with patch.object(
        chom.urllib.request, "urlopen", return_value=fake_response(payload)
    ):
        params = chom.station_parameters("07486")
    assert params == ("air_temperature", "wind_speed")


def test_empty_result_is_legitimate():
    with patch.object(
        chom.urllib.request, "urlopen", return_value=fake_response({"stations": []})
    ):
        assert chom.search_stations("nowhere") == []
