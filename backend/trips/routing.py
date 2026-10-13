"""HERE Routing v8 (truck mode) and HERE Geocoding, plus the 3-route fallback."""

from dataclasses import dataclass

import flexpolyline
import requests
from django.conf import settings

from trips.geometry import (
    Point,
    bearing_deg,
    cumulative_miles,
    downsample,
    haversine_mi,
    offset_point,
    point_at_mile,
    sample_miles,
)

ROUTER_URL = "https://router.hereapi.com/v8/routes"
GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
REQUEST_TIMEOUT_S = 15
METERS_PER_MILE = 1609.344
KG_PER_LB = 0.45359237
# Typical empty tractor-trailer.
TARE_WEIGHT_LB = 35000
# US federal gross weight limit without a permit.
LEGAL_GROSS_LB = 80000
MAX_LOAD_LB = 80000
# A detour point sits 15% of the route length off the middle of the main route.
VIA_OFFSET_SHARE = 0.15
# About 2 km. A detour with 80% of its points this close to another route is a copy.
DUPLICATE_DISTANCE_MI = 1.25
DUPLICATE_SHARE = 0.8


class RoutingError(Exception):
    """HERE could not be reached or returned an error."""


class NoRouteFound(RoutingError):
    """HERE answered, but there is no truck route between the two places."""


@dataclass(frozen=True)
class RouteGeometry:
    """One route: its line, and the travel time of each stretch of it."""

    points: list[Point]
    # Index in `points` where each span starts, and how long each span takes.
    span_offsets: list[int]
    span_durations_s: list[float]
    duration_s: float
    distance_mi: float


def gross_weight_lb(load_lb: float) -> float:
    """Cargo plus the empty truck."""
    return load_lb + TARE_WEIGHT_LB


def _api_key() -> str:
    if not settings.HERE_API_KEY:
        raise RoutingError("HERE_API_KEY is not set.")
    return settings.HERE_API_KEY


def _get_json(url: str, params: dict) -> dict:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as error:
        # The error text contains the full URL, including the apiKey, so only keep the error type.
        # "from None" also drops the original error, so it cannot end up in logs.
        raise RoutingError(
            f"Routing service unreachable ({type(error).__name__})."
        ) from None
    if response.status_code != 200:
        raise RoutingError(f"Routing service returned {response.status_code}.")
    return response.json()


def geocode(query: str) -> list[dict]:
    """Place suggestions for the autocomplete, limited to the US and Canada."""
    payload = _get_json(
        GEOCODE_URL,
        {"q": query, "in": "countryCode:USA,CAN", "limit": 5, "apiKey": _api_key()},
    )
    return [
        {
            "label": item["address"]["label"],
            "lat": item["position"]["lat"],
            "lon": item["position"]["lng"],
        }
        for item in payload.get("items", [])
    ]


def _parse_route(route_payload: dict) -> RouteGeometry:
    points: list[Point] = []
    span_offsets: list[int] = []
    span_durations_s: list[float] = []
    duration_s = 0.0
    length_m = 0.0
    for section_payload in route_payload["sections"]:
        section_points = [
            (coordinate[0], coordinate[1])
            for coordinate in flexpolyline.decode(section_payload["polyline"])
        ]
        base_index = len(points)
        if points and section_points and points[-1] == section_points[0]:
            # Sections share their joining point, so keep only one copy.
            base_index -= 1
            section_points = section_points[1:]
        points.extend(section_points)
        for span in section_payload.get("spans", []):
            span_offsets.append(base_index + span["offset"])
            span_durations_s.append(float(span.get("duration", 0)))
        duration_s += section_payload["summary"]["duration"]
        length_m += section_payload["summary"]["length"]
    return RouteGeometry(
        points,
        span_offsets,
        span_durations_s,
        float(duration_s),
        length_m / METERS_PER_MILE,
    )


def fetch_routes(
    origin: Point,
    destination: Point,
    departure_utc,
    load_lb: float,
    via: Point | None = None,
) -> list[RouteGeometry]:
    """Ask HERE for truck routes. Without `via` we ask for 2 alternatives, with `via` for one detour."""
    params = {
        "transportMode": "truck",
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "departureTime": departure_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "return": "polyline,summary",
        "spans": "duration",
        # HERE wants the truck weight in kilograms.
        "vehicle[grossWeight]": round(gross_weight_lb(load_lb) * KG_PER_LB),
        "apiKey": _api_key(),
    }
    if via is None:
        params["alternatives"] = 2
    else:
        params["via"] = f"{via[0]},{via[1]}!passThrough=true"
    payload = _get_json(ROUTER_URL, params)
    routes = [
        _parse_route(route_payload) for route_payload in payload.get("routes", [])
    ]
    if not routes:
        raise NoRouteFound("No truck route was found between these places.")
    return routes


def _is_duplicate(candidate: RouteGeometry, existing: RouteGeometry) -> bool:
    """True when most of the candidate runs within ~2 km of an existing route."""
    existing_points = downsample(
        existing.points, cumulative_miles(existing.points), 1.0
    )
    candidate_cumulative = cumulative_miles(candidate.points)
    samples = [
        point_at_mile(candidate.points, candidate_cumulative, mile)
        for mile in sample_miles(candidate_cumulative[-1], 5.0)
    ]
    near_count = sum(
        1
        for sample in samples
        if min(
            haversine_mi(sample, existing_point) for existing_point in existing_points
        )
        <= DUPLICATE_DISTANCE_MI
    )
    return near_count / len(samples) >= DUPLICATE_SHARE


def get_route_options(
    origin: Point, destination: Point, departure_utc, load_lb: float, wanted: int = 3
) -> tuple[list[RouteGeometry], str | None]:
    """Up to `wanted` distinct routes, and a note when fewer were found."""
    routes = fetch_routes(origin, destination, departure_utc, load_lb)[:wanted]
    if len(routes) < wanted:
        main_route = routes[0]
        main_cumulative = cumulative_miles(main_route.points)
        half_mile = main_cumulative[-1] / 2
        midpoint = point_at_mile(main_route.points, main_cumulative, half_mile)
        # Direction of travel in the middle of the route, to know which way is "sideways".
        heading = bearing_deg(
            point_at_mile(main_route.points, main_cumulative, half_mile - 5),
            point_at_mile(main_route.points, main_cumulative, half_mile + 5),
        )
        # Try one detour to the left (-90 degrees) and one to the right (+90 degrees).
        for side in (-90, 90):
            if len(routes) >= wanted:
                break
            via = offset_point(
                midpoint, heading + side, main_cumulative[-1] * VIA_OFFSET_SHARE
            )
            try:
                candidates = fetch_routes(
                    origin, destination, departure_utc, load_lb, via=via
                )
            except RoutingError:
                continue
            if not any(_is_duplicate(candidates[0], existing) for existing in routes):
                routes.append(candidates[0])
    note = None
    if len(routes) < wanted:
        note = f"Only {len(routes)} distinct route(s) found between these places."
    return routes, note
