"""Points around the routes for the heatmap, and the weather forecast for them."""

from datetime import UTC, datetime, timedelta
from typing import Any

from trips.geometry import (
    Point,
    bearing_deg,
    cumulative_miles,
    offset_point,
    point_at_mile,
    sample_miles,
)
from trips.risk import assess, effective_wind
from trips.weather import fetch_series, round_coord, sample_at

# A grid point every 15.5 miles (about 25 km) along each route.
GRID_SPACING_MI = 15.5
# And one on each side of the road, 25 miles (about 40 km) away.
SIDE_OFFSET_MI = 25.0
# Open-Meteo takes about half a second per location, so the grid is kept small.
MAX_GRID_POINTS = 120
# The heatmap slider covers now plus 48 hours, one step per hour.
FORECAST_HOURS = 48
# 3 forecast days cover now plus 48 hours from any time of the day.
CORRIDOR_FORECAST_DAYS = 3


def build_grid(
    routes_points: list[list[Point]], spacing_mi: float = GRID_SPACING_MI
) -> list[Point]:
    """Points along every route plus a copy on each side, rounded and without duplicates."""
    while True:
        # A dict keeps the points unique and in order.
        grid: dict[Point, None] = {}
        for points in routes_points:
            cumulative = cumulative_miles(points)
            total_mi = cumulative[-1]
            for mile in sample_miles(total_mi, spacing_mi):
                center = point_at_mile(points, cumulative, mile)
                # Direction of travel here, to know which way is "left" and "right".
                heading = bearing_deg(
                    point_at_mile(points, cumulative, max(mile - 1, 0)),
                    point_at_mile(points, cumulative, min(mile + 1, total_mi)),
                )
                for candidate in (
                    center,
                    offset_point(center, heading - 90, SIDE_OFFSET_MI),
                    offset_point(center, heading + 90, SIDE_OFFSET_MI),
                ):
                    grid[round_coord(*candidate)] = None
        if len(grid) <= MAX_GRID_POINTS:
            return list(grid)
        # Too many points for one weather request. Space them out and try again.
        spacing_mi *= 1.5


def forecast_corridor(
    grid_points: list[list[float]], load_lb: float, now_utc: datetime | None = None
) -> dict[str, Any]:
    """Hour by hour weather and risk for every grid point, from the current hour to +48 h.

    Each result list has one row per hour and one value per point (None when unknown),
    so the frontend can switch hours without calling the server again.
    """
    now_utc = now_utc or datetime.now(UTC)
    start_utc = now_utc.replace(minute=0, second=0, microsecond=0)
    coords = [round_coord(lat, lon) for lat, lon in grid_points]
    series_by_coord = fetch_series(coords, CORRIDOR_FORECAST_DAYS)

    risk_by_hour, wind_by_hour, rain_by_hour, snow_by_hour = [], [], [], []
    for hour_offset in range(FORECAST_HOURS + 1):
        moment = start_utc + timedelta(hours=hour_offset)
        risk_row, wind_row, rain_row, snow_row = [], [], [], []
        for coord in coords:
            series = series_by_coord.get(coord)
            sample = sample_at(series, moment) if series else None
            if sample is None:
                for row in (risk_row, wind_row, rain_row, snow_row):
                    row.append(None)
                continue
            # The same risk rules as the route checkpoints, with the same load.
            risk_row.append(int(assess(sample, load_lb).level))
            wind_row.append(round(effective_wind(sample), 1))
            rain_row.append(round(sample.rain_in, 2))
            snow_row.append(round(sample.snow_in, 2))
        risk_by_hour.append(risk_row)
        wind_by_hour.append(wind_row)
        rain_by_hour.append(rain_row)
        snow_by_hour.append(snow_row)

    return {
        "start": start_utc.isoformat().replace("+00:00", "Z"),
        # [lon, lat] order, as the map expects.
        "points": [[lon, lat] for lat, lon in coords],
        "risk": risk_by_hour,
        "wind": wind_by_hour,
        "rain": rain_by_hour,
        "snow": snow_by_hour,
    }
