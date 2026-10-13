from datetime import UTC, datetime
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase

from trips.tests.factories import series_from
from trips.weather import WeatherUnavailable, fetch_series, sample_at


def open_meteo_payload(wind):
    return {
        "hourly": {
            "time": ["2026-10-14T00:00", "2026-10-14T01:00"],
            "wind_speed_10m": [wind, wind],
            "wind_gusts_10m": [wind + 5, wind + 5],
            "rain": [0.0, 0.1],
            "showers": [0.0, 0.05],
            "snowfall": [0.0, 0.0],
        }
    }


class FetchSeriesTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("trips.weather.requests.get")
    def test_batch_request_and_rounding(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [open_meteo_payload(10), open_meteo_payload(20)],
        )
        result = fetch_series(
            [(41.8781, -87.6298), (39.7392, -104.9903)], forecast_days=2
        )
        self.assertEqual(set(result), {(41.9, -87.6), (39.7, -105.0)})
        self.assertEqual(result[(39.7, -105.0)].wind_mph[0], 20)
        self.assertEqual(mock_get.call_count, 1)

    @patch("trips.weather.requests.get")
    def test_single_location_response_is_a_dict(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200, json=lambda: open_meteo_payload(10)
        )
        result = fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertEqual(
            result[(41.9, -87.6)].start_utc, datetime(2026, 10, 14, tzinfo=UTC)
        )

    @patch("trips.weather.requests.get")
    def test_second_call_uses_cache(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200, json=lambda: open_meteo_payload(10)
        )
        fetch_series([(41.88, -87.63)], forecast_days=2)
        fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertEqual(mock_get.call_count, 1)

    @patch("trips.weather.requests.get")
    def test_http_error_raises_weather_unavailable(self, mock_get):
        mock_get.return_value = Mock(status_code=429, json=lambda: {"reason": "limit"})
        with self.assertRaises(WeatherUnavailable):
            fetch_series([(41.88, -87.63)], forecast_days=2)


class SampleAtTests(SimpleTestCase):
    def setUp(self):
        self.series = series_from(datetime(2026, 10, 14, tzinfo=UTC), hours=24)
        self.series.rain_in[11] = 0.2
        self.series.showers_in[11] = 0.05

    def test_uses_the_hour_that_ends_after_arrival(self):
        sample = sample_at(self.series, datetime(2026, 10, 14, 10, 20, tzinfo=UTC))
        assert sample is not None
        self.assertAlmostEqual(sample.rain_in, 0.25)

    def test_on_the_hour_uses_that_hour(self):
        sample = sample_at(self.series, datetime(2026, 10, 14, 11, 0, tzinfo=UTC))
        assert sample is not None
        self.assertAlmostEqual(sample.rain_in, 0.25)

    def test_outside_range_is_none(self):
        self.assertIsNone(
            sample_at(self.series, datetime(2026, 10, 13, 22, tzinfo=UTC))
        )
        self.assertIsNone(sample_at(self.series, datetime(2026, 10, 15, 1, tzinfo=UTC)))
