from datetime import UTC, datetime
from unittest.mock import Mock, patch

import flexpolyline
import requests
from django.test import SimpleTestCase, override_settings

from trips.routing import NoRouteFound, RoutingError, fetch_routes, get_route_options
from trips.tests.factories import straight_points, straight_route

DEPARTURE = datetime(2026, 10, 14, 13, tzinfo=UTC)
ORIGIN, DESTINATION = (41.0, -100.0), (41.0, -96.0)


def section(points, duration_s=3600, length_m=10000):
    return {
        "polyline": flexpolyline.encode(points),
        "summary": {"duration": duration_s, "length": length_m},
        "spans": [{"offset": 0, "duration": duration_s}],
    }


@override_settings(HERE_API_KEY="test-key")
class FetchRoutesTests(SimpleTestCase):
    @patch("trips.routing.requests.get")
    def test_parses_points_spans_and_miles(self, mock_get):
        points = straight_points(ORIGIN, DESTINATION, steps=10)
        mock_get.return_value = Mock(
            status_code=200, json=lambda: {"routes": [{"sections": [section(points)]}]}
        )
        routes = fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=20000)
        self.assertEqual(len(routes[0].points), 11)
        self.assertEqual(routes[0].span_offsets, [0])
        self.assertAlmostEqual(routes[0].distance_mi, 6.21, places=2)
        sent_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(
            sent_params["vehicle[grossWeight]"], round((20000 + 35000) * 0.45359237)
        )

    @patch("trips.routing.requests.get")
    def test_joins_sections_without_duplicate_point(self, mock_get):
        first = straight_points(ORIGIN, (41.0, -98.0), steps=4)
        second = straight_points((41.0, -98.0), DESTINATION, steps=4)
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {"routes": [{"sections": [section(first), section(second)]}]},
        )
        route = fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)[0]
        self.assertEqual(len(route.points), 9)
        self.assertEqual(route.span_offsets, [0, 4])
        self.assertEqual(route.duration_s, 7200)

    @patch("trips.routing.requests.get")
    def test_http_error_raises(self, mock_get):
        mock_get.return_value = Mock(
            status_code=401, json=lambda: {"title": "Unauthorized"}
        )
        with self.assertRaises(RoutingError):
            fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)

    @patch("trips.routing.requests.get")
    def test_network_error_does_not_leak_the_api_key(self, mock_get):
        # requests puts the full URL, including apiKey, in its error text.
        mock_get.side_effect = requests.ConnectionError(
            "failed: /v8/routes?apiKey=test-key"
        )
        with self.assertRaises(RoutingError) as context:
            fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)
        self.assertNotIn("test-key", str(context.exception))
        self.assertIsNone(context.exception.__cause__)

    @patch("trips.routing.requests.get")
    def test_empty_routes_raise_no_route(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {"routes": []})
        with self.assertRaises(NoRouteFound):
            fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)

    @override_settings(HERE_API_KEY="")
    def test_missing_key_raises(self):
        with self.assertRaises(RoutingError):
            fetch_routes(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)


class RouteOptionsTests(SimpleTestCase):
    @patch("trips.routing.fetch_routes")
    def test_adds_detours_until_three_routes(self, mock_fetch):
        main = straight_route(ORIGIN, DESTINATION)

        def fake_fetch(origin, destination, departure_utc, load_lb, via=None):
            return [main] if via is None else [straight_route(origin, via, steps=100)]

        mock_fetch.side_effect = fake_fetch
        routes, note = get_route_options(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)
        self.assertEqual(len(routes), 3)
        self.assertIsNone(note)

    @patch("trips.routing.fetch_routes")
    def test_drops_detours_that_copy_the_main_route(self, mock_fetch):
        mock_fetch.return_value = [straight_route(ORIGIN, DESTINATION)]
        routes, note = get_route_options(ORIGIN, DESTINATION, DEPARTURE, load_lb=0)
        self.assertEqual(len(routes), 1)
        assert note is not None
        self.assertIn("Only 1", note)
