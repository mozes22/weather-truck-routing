from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from trips.corridor import MAX_GRID_POINTS, build_grid, forecast_corridor
from trips.tests.factories import series_from, straight_points

NOW = datetime(2026, 10, 14, 10, 25, tzinfo=UTC)


class BuildGridTests(SimpleTestCase):
    def test_grid_has_center_and_side_points_and_respects_cap(self):
        grid = build_grid([straight_points((41.0, -110.0), (41.0, -80.0), steps=600)])
        self.assertLessEqual(len(grid), MAX_GRID_POINTS)
        self.assertTrue(any(lat > 41.2 for lat, _ in grid))
        self.assertTrue(any(lat < 40.8 for lat, _ in grid))


def stormy_after_noon(coords, forecast_days):
    result = {}
    for coord in coords:
        series = series_from(datetime(2026, 10, 14, tzinfo=UTC), hours=72)
        for hour_index in range(12, 72):
            series.gust_mph[hour_index] = 50.0
        result[coord] = series
    return result


@patch("trips.corridor.fetch_series", side_effect=stormy_after_noon)
class ForecastCorridorTests(SimpleTestCase):
    def test_shapes_and_values(self, _mock_series):
        result = forecast_corridor(
            [[41.0, -100.0], [41.5, -99.0]], load_lb=20000, now_utc=NOW
        )
        self.assertEqual(result["start"], "2026-10-14T10:00:00Z")
        self.assertEqual(result["points"], [[-100.0, 41.0], [-99.0, 41.5]])
        self.assertEqual(len(result["risk"]), 49)
        self.assertEqual(result["risk"][0], [0, 0])
        self.assertEqual(result["risk"][2], [3, 3])
        self.assertEqual(result["wind"][2], [50.0, 50.0])

    def test_endpoint(self, _mock_series):
        response: Any = APIClient().post(
            "/api/corridor-forecast",
            {"points": [[41.0, -100.0]], "load_lb": 20000},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["risk"]), 49)

    def test_endpoint_rejects_bad_points(self, _mock_series):
        response: Any = APIClient().post(
            "/api/corridor-forecast",
            {"points": [[41.0]], "load_lb": 20000},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
