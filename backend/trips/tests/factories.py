"""Small builders for fake routes and forecasts used across tests."""

from trips.geometry import cumulative_miles
from trips.routing import RouteGeometry
from trips.weather import HourlySeries


def series_from(start_utc, hours=400, wind=5.0, gust=8.0, rain=0.0, snow=0.0):
    return HourlySeries(
        start_utc=start_utc,
        wind_mph=[wind] * hours,
        gust_mph=[gust] * hours,
        rain_in=[rain] * hours,
        showers_in=[0.0] * hours,
        snow_in=[snow] * hours,
    )


def straight_points(start, end, steps=200):
    return [
        (
            start[0] + (end[0] - start[0]) * step / steps,
            start[1] + (end[1] - start[1]) * step / steps,
        )
        for step in range(steps + 1)
    ]


def straight_route(start, end, hours=10.0, steps=200):
    points = straight_points(start, end, steps)
    return RouteGeometry(
        points=points,
        span_offsets=[0],
        span_durations_s=[hours * 3600],
        duration_s=hours * 3600,
        distance_mi=cumulative_miles(points)[-1],
    )
