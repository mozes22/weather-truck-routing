from datetime import UTC, datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from trips.planner import plan_trip
from trips.tests.factories import series_from, straight_route
from trips.weather import WeatherUnavailable

NOW = datetime(2026, 10, 14, 10, tzinfo=UTC)
DEPARTURE = datetime(2026, 10, 14, 13, tzinfo=UTC)
ORIGIN = {"label": "West", "lat": 41.0, "lon": -100.0}
DESTINATION = {"label": "East", "lat": 41.0, "lon": -96.0}


def windy_north(coords, forecast_days):
    """Gusts of 50 mph north of latitude 42, calm elsewhere."""
    return {
        coord: series_from(
            datetime(2026, 10, 14, tzinfo=UTC), gust=50.0 if coord[0] > 42 else 8.0
        )
        for coord in coords
    }


def run_plan(**overrides):
    arguments = {
        "driver_name": "Ahmad",
        "origin": ORIGIN,
        "destination": DESTINATION,
        "departure_utc": DEPARTURE,
        "timezone_name": "America/Chicago",
        "load_lb": 20000,
        "interval_mi": 25,
        "now_utc": NOW,
    }
    arguments.update(overrides)
    return plan_trip(**arguments)


def calm_route(hours=5):
    return straight_route((41.0, -100.0), (41.0, -96.0), hours=hours)


@patch("trips.planner.fetch_series", side_effect=windy_north)
@patch("trips.planner.get_route_options")
class PlanTripTests(SimpleTestCase):
    def test_recommends_calm_route_over_faster_windy_one(
        self, mock_options, _mock_series
    ):
        windy = straight_route((43.0, -100.0), (43.0, -96.0), hours=4)
        mock_options.return_value = ([windy, calm_route()], None)
        result = run_plan()
        self.assertEqual(result["recommended_route_id"], "B")
        route_a = result["routes"][0]
        self.assertAlmostEqual(
            route_a["summary"]["severe_mi"], route_a["distance_mi"], delta=0.5
        )
        self.assertTrue(
            any("Ahmad" in warning["message"] for warning in result["warnings"])
        )
        self.assertTrue(result["corridor_grid"])

    def test_checkpoints_cover_route_and_follow_interval(
        self, mock_options, _mock_series
    ):
        mock_options.return_value = (
            [calm_route()],
            "Only 1 distinct route(s) found between these places.",
        )
        route = run_plan()["routes"][0]
        self.assertEqual(
            [checkpoint["mile"] for checkpoint in route["checkpoints"]][:3], [0, 25, 50]
        )
        self.assertAlmostEqual(
            sum(checkpoint["covered_mi"] for checkpoint in route["checkpoints"]),
            route["distance_mi"],
            delta=0.05,
        )

    def test_long_trip_gets_rest_stops_and_later_arrival(
        self, mock_options, _mock_series
    ):
        mock_options.return_value = ([calm_route(hours=12)], None)
        route = run_plan()["routes"][0]
        self.assertEqual([stop["kind"] for stop in route["stops"]], ["break", "rest"])
        self.assertEqual(route["duration_s"], 22.5 * 3600)
        self.assertEqual(route["arrival"], "2026-10-15T11:30:00Z")

    def test_overweight_cargo_gives_warning_not_error(self, mock_options, _mock_series):
        mock_options.return_value = ([calm_route()], None)
        result = run_plan(load_lb=50000)
        self.assertTrue(
            any("85,000 lb" in warning["message"] for warning in result["warnings"])
        )


@patch("trips.planner.get_route_options")
class WeatherDownTests(SimpleTestCase):
    @patch("trips.planner.fetch_series", side_effect=WeatherUnavailable("down"))
    def test_plan_survives_without_weather(self, _mock_series, mock_options):
        mock_options.return_value = ([calm_route()], None)
        result = run_plan()
        self.assertEqual(
            {checkpoint["level"] for checkpoint in result["routes"][0]["checkpoints"]},
            {"unknown"},
        )
        self.assertTrue(
            any(
                "weather" in warning["message"].lower()
                for warning in result["warnings"]
            )
        )
