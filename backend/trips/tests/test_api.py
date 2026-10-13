from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from trips.routing import NoRouteFound, RoutingError

CHICAGO = {"label": "Chicago, IL", "lat": 41.8781, "lon": -87.6298}
DENVER = {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903}


def chicago_local(days=1):
    local_time = datetime.now(ZoneInfo("America/Chicago")) + timedelta(days=days)
    return local_time.strftime("%Y-%m-%dT%H:00")


def plan_payload(**overrides):
    payload = {
        "driver_name": "Ahmad",
        "origin": CHICAGO,
        "destination": DENVER,
        "departure": chicago_local(),
        "load_lb": 30000,
        "interval_mi": 25,
    }
    payload.update(overrides)
    return payload


class PlanEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    # Any: DRF has no type stubs, so the checker would guess the wrong response type.
    def post(self, **overrides) -> Any:
        return self.client.post("/api/plan", plan_payload(**overrides), format="json")

    @patch("trips.planner.plan_trip", return_value={"routes": []})
    def test_valid_request_calls_planner_with_utc_departure(self, mock_plan):
        self.assertEqual(self.post().status_code, 200)
        call_arguments = mock_plan.call_args.kwargs
        self.assertEqual(call_arguments["timezone_name"], "America/Chicago")
        self.assertEqual(call_arguments["departure_utc"].utcoffset(), timedelta(0))
        self.assertEqual(call_arguments["interval_mi"], 25)

    @patch("trips.planner.plan_trip", return_value={"routes": []})
    def test_heavy_cargo_is_accepted(self, _mock_plan):
        self.assertEqual(self.post(load_lb=60000).status_code, 200)

    def test_rejects_same_origin_and_destination(self):
        response = self.post(destination=CHICAGO)
        self.assertEqual(response.status_code, 400)
        self.assertIn("destination", response.json())

    def test_rejects_past_departure(self):
        response = self.post(departure="2020-01-01T08:00")
        self.assertEqual(response.status_code, 400)
        self.assertIn("departure", response.json())

    def test_rejects_departure_more_than_five_days_out(self):
        self.assertEqual(self.post(departure=chicago_local(days=6)).status_code, 400)

    def test_rejects_load_above_80000(self):
        response = self.post(load_lb=90000)
        self.assertEqual(response.status_code, 400)
        self.assertIn("load_lb", response.json())

    def test_rejects_unknown_interval(self):
        self.assertEqual(self.post(interval_mi=30).status_code, 400)

    @patch("trips.planner.plan_trip", side_effect=RoutingError("HERE down"))
    def test_routing_failure_is_502(self, _mock_plan):
        self.assertEqual(self.post().status_code, 502)

    @patch("trips.planner.plan_trip", side_effect=NoRouteFound("No truck route"))
    def test_no_route_is_422(self, _mock_plan):
        self.assertEqual(self.post().status_code, 422)


class GeocodeEndpointTests(SimpleTestCase):
    @patch("trips.routing.geocode", return_value=[CHICAGO])
    def test_returns_places(self, _mock_geocode):
        response: Any = APIClient().get("/api/geocode", {"q": "Chicago"})
        self.assertEqual(response.json(), [CHICAGO])

    def test_short_query_returns_empty_list(self):
        response: Any = APIClient().get("/api/geocode", {"q": "Ch"})
        self.assertEqual(response.json(), [])
