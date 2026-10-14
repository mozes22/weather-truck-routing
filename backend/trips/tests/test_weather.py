from datetime import UTC, datetime
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase

from trips.tests.factories import series_from
from trips.weather import (
    MAX_FORECAST_DAYS,
    WeatherUnavailable,
    fetch_series,
    forecast_days_until,
    sample_at,
)


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


@patch("trips.weather.time.sleep")
@patch("trips.weather.requests.get")
class RetryTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_retries_once_after_503(self, mock_get, _mock_sleep):
        mock_get.side_effect = [
            Mock(status_code=503, json=lambda: {}),
            Mock(status_code=200, json=lambda: open_meteo_payload(10)),
        ]
        result = fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertIn((41.9, -87.6), result)
        self.assertEqual(mock_get.call_count, 2)

    def test_retries_once_after_timeout(self, mock_get, _mock_sleep):
        mock_get.side_effect = [
            requests.Timeout(),
            Mock(status_code=200, json=lambda: open_meteo_payload(10)),
        ]
        result = fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertIn((41.9, -87.6), result)
        self.assertEqual(mock_get.call_count, 2)

    def test_gives_up_after_the_second_failure(self, mock_get, _mock_sleep):
        mock_get.side_effect = [
            Mock(status_code=503, json=lambda: {}),
            Mock(status_code=503, json=lambda: {}),
        ]
        with self.assertRaises(WeatherUnavailable):
            fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertEqual(mock_get.call_count, 2)

    def test_does_not_retry_a_rate_limit(self, mock_get, _mock_sleep):
        mock_get.return_value = Mock(status_code=429, json=lambda: {})
        with self.assertRaises(WeatherUnavailable):
            fetch_series([(41.88, -87.63)], forecast_days=2)
        self.assertEqual(mock_get.call_count, 1)


class ForecastDaysUntilTests(SimpleTestCase):
    NOW = datetime(2026, 10, 14, 10, 25, tzinfo=UTC)

    def test_a_moment_today_needs_one_day(self):
        self.assertEqual(forecast_days_until(self.NOW, self.NOW), 1)

    def test_covers_the_hours_already_passed_today(self):
        # 48 h ahead is exactly 2 days, plus the extra day for today's past hours.
        later = datetime(2026, 10, 16, 10, 25, tzinfo=UTC)
        self.assertEqual(forecast_days_until(later, self.NOW), 3)

    def test_a_partial_day_rounds_up(self):
        later = datetime(2026, 10, 15, 11, 0, tzinfo=UTC)
        self.assertEqual(forecast_days_until(later, self.NOW), 3)

    def test_never_more_than_open_meteo_allows(self):
        later = datetime(2026, 12, 1, tzinfo=UTC)
        self.assertEqual(forecast_days_until(later, self.NOW), MAX_FORECAST_DAYS)

    def test_a_moment_in_the_past_still_needs_one_day(self):
        earlier = datetime(2026, 10, 10, tzinfo=UTC)
        self.assertEqual(forecast_days_until(earlier, self.NOW), 1)


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
