"""Builds a full trip plan: routes, checkpoints, ETAs, weather risk, ranking, warnings."""

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from trips.corridor import build_grid
from trips.geometry import (
    covered_miles,
    cumulative_miles,
    downsample,
    interpolate,
    point_at_mile,
    sample_miles,
)
from trips.hos import elapsed_seconds, plan_stops
from trips.risk import (
    LEVEL_KEYS,
    LEVEL_LABELS,
    RiskLevel,
    assess,
    effective_wind,
    rank_routes,
    recommendation_reason,
    summarize_route,
)
from trips.routing import LEGAL_GROSS_LB, get_route_options, gross_weight_lb
from trips.timeline import cumulative_driving_seconds
from trips.weather import WeatherUnavailable, fetch_series, round_coord, sample_at

# A route is a plain dict, because it is sent to the frontend as JSON.
Route = dict[str, Any]

ROUTE_IDS = ("A", "B", "C")
# Open-Meteo forecasts at most 16 days ahead.
MAX_FORECAST_DAYS = 16
# Spacing of the points of the line drawn on the map. Smaller means smoother and heavier.
MAP_LINE_STEP_MI = 0.3


def to_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _build_route(
    route_id: str, geometry, departure_utc: datetime, interval_mi: float
) -> Route:
    """One route with its checkpoints and rest stops. The weather is added later."""
    cumulative = cumulative_miles(geometry.points)
    driving_s = cumulative_driving_seconds(
        cumulative,
        geometry.span_offsets,
        geometry.span_durations_s,
        geometry.duration_s,
    )
    total_driving_s = driving_s[-1]
    stops = plan_stops(total_driving_s)

    sampled_miles = sample_miles(cumulative[-1], interval_mi)
    checkpoints = []
    for mile, covered_mi in zip(sampled_miles, covered_miles(sampled_miles)):
        lat, lon = point_at_mile(geometry.points, cumulative, mile)
        driving_at_mile = interpolate(cumulative, driving_s, mile)
        checkpoints.append(
            {
                "mile": round(mile, 2),
                "lat": lat,
                "lon": lon,
                "covered_mi": covered_mi,
                # Arrival time = departure + driving time + the breaks and rests before it.
                "eta": departure_utc
                + timedelta(seconds=elapsed_seconds(driving_at_mile, stops)),
            }
        )

    stop_payloads = []
    for stop in stops:
        stop_mile = interpolate(driving_s, cumulative, stop.driving_s_at)
        lat, lon = point_at_mile(geometry.points, cumulative, stop_mile)
        stop_payloads.append(
            {
                "kind": stop.kind,
                "mile": round(stop_mile, 1),
                "lat": lat,
                "lon": lon,
                "start": to_iso(
                    departure_utc
                    + timedelta(seconds=elapsed_seconds(stop.driving_s_at, stops))
                ),
                "duration_min": round(stop.duration_s / 60),
            }
        )

    total_elapsed_s = elapsed_seconds(total_driving_s, stops)
    return {
        "id": route_id,
        "points": geometry.points,
        "distance_mi": round(cumulative[-1], 1),
        "driving_s": round(total_driving_s),
        "duration_s": round(total_elapsed_s),
        "arrival": to_iso(departure_utc + timedelta(seconds=total_elapsed_s)),
        # [lon, lat] order, as the map expects.
        "coordinates": [
            [lon, lat]
            for lat, lon in downsample(geometry.points, cumulative, MAP_LINE_STEP_MI)
        ],
        "checkpoints": checkpoints,
        "stops": stop_payloads,
    }


def _attach_weather(
    routes: list[Route], load_lb: float, now_utc: datetime
) -> str | None:
    """Adds level, reasons and weather to every checkpoint. Returns an error text if weather failed."""
    all_checkpoints = [
        checkpoint for route in routes for checkpoint in route["checkpoints"]
    ]
    last_eta = max(checkpoint["eta"] for checkpoint in all_checkpoints)
    # Ask for enough forecast days to reach the last arrival.
    forecast_days = max(
        1,
        min(
            MAX_FORECAST_DAYS,
            math.ceil((last_eta - now_utc).total_seconds() / 86400) + 1,
        ),
    )
    coords = [
        round_coord(checkpoint["lat"], checkpoint["lon"])
        for checkpoint in all_checkpoints
    ]

    weather_problem = None
    try:
        series_by_coord = fetch_series(coords, forecast_days)
    except WeatherUnavailable as error:
        series_by_coord = {}
        weather_problem = str(error)

    for checkpoint in all_checkpoints:
        series = series_by_coord.get(round_coord(checkpoint["lat"], checkpoint["lon"]))
        sample = sample_at(series, checkpoint["eta"]) if series else None
        if sample is None:
            # No forecast for this checkpoint: it stays "unknown" and the plan still works.
            checkpoint.update(
                {
                    "level_value": None,
                    "level": "unknown",
                    "reasons": [],
                    "weather": None,
                }
            )
            continue
        assessment = assess(sample, load_lb)
        checkpoint.update(
            {
                "level_value": assessment.level,
                "level": LEVEL_KEYS[assessment.level],
                "reasons": list(assessment.reasons),
                "weather": {
                    "wind_mph": round(sample.wind_mph, 1),
                    "gust_mph": (
                        None if sample.gust_mph is None else round(sample.gust_mph, 1)
                    ),
                    "effective_wind_mph": round(effective_wind(sample), 1),
                    "rain_in": round(sample.rain_in, 2),
                    "snow_in": round(sample.snow_in, 2),
                },
            }
        )
    return weather_problem


def _danger_stretches(checkpoints: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Consecutive checkpoints at Severe or No Travel, grouped together."""
    stretches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        if (
            checkpoint["level_value"] is not None
            and checkpoint["level_value"] >= RiskLevel.SEVERE
        ):
            current.append(checkpoint)
        elif current:
            stretches.append(current)
            current = []
    if current:
        stretches.append(current)
    return stretches


def _build_warnings(
    driver: str,
    routes_by_id: dict[str, Route],
    summaries_by_id,
    recommended_id: str,
    timezone_name: str,
    load_lb: float,
    route_note: str | None,
    weather_problem: str | None,
) -> list[dict[str, str]]:
    """Messages for the driver, addressed by name."""
    zone = ZoneInfo(timezone_name)
    warnings = []
    gross_lb = gross_weight_lb(load_lb)
    if gross_lb > LEGAL_GROSS_LB:
        warnings.append(
            {
                "severity": "warning",
                "message": (
                    f"{driver}, {load_lb:,} lb of cargo puts the truck at about {gross_lb:,.0f} lb "
                    f"gross, over the {LEGAL_GROSS_LB:,} lb federal limit. "
                    "You'll need an overweight permit."
                ),
            }
        )
    if weather_problem:
        warnings.append(
            {
                "severity": "warning",
                "message": (
                    f"{driver}, weather data is unavailable right now, so risk is unknown. "
                    f"({weather_problem})"
                ),
            }
        )

    recommended = routes_by_id[recommended_id]
    for stretch in _danger_stretches(recommended["checkpoints"]):
        worst = max(checkpoint["level_value"] for checkpoint in stretch)
        reasons = sorted(
            {reason for checkpoint in stretch for reason in checkpoint["reasons"]}
        )
        miles = sum(checkpoint["covered_mi"] for checkpoint in stretch)
        when = stretch[0]["eta"].astimezone(zone).strftime("%a %H:%M %Z")
        message = (
            f"{driver}, route {recommended_id} has {miles:.0f} mi of {LEVEL_LABELS[worst]} "
            f"conditions between mile {stretch[0]['mile']:.0f} and {stretch[-1]['mile']:.0f}, "
            f"around {when} ({' + '.join(reasons)})."
        )
        if "load" in reasons:
            message += f" Your {load_lb:,} lb load makes the wind limit stricter."
        warnings.append(
            {
                "severity": "error" if worst == RiskLevel.NO_TRAVEL else "warning",
                "message": message,
            }
        )

    if all(summary.no_travel_mi > 0 for summary in summaries_by_id.values()):
        warnings.append(
            {
                "severity": "error",
                "message": (
                    f"{driver}, every route crosses No Travel conditions. Consider delaying "
                    "departure; the heatmap shows when it clears."
                ),
            }
        )

    recommended_summary = summaries_by_id[recommended_id]
    if recommended_summary.unknown_mi > 0 and not weather_problem:
        warnings.append(
            {
                "severity": "info",
                "message": (
                    f"{driver}, {recommended_summary.unknown_mi:.0f} mi of route {recommended_id} "
                    "are beyond the forecast range, so their risk is unknown."
                ),
            }
        )
    if route_note:
        warnings.append({"severity": "info", "message": route_note})
    if (
        not weather_problem
        and recommended_summary.unknown_mi == 0
        and recommended_summary.no_travel_mi
        == recommended_summary.severe_mi
        == recommended_summary.high_mi
        == 0
    ):
        warnings.append(
            {
                "severity": "success",
                "message": f"{driver}, route {recommended_id} looks clear: no High, Severe or No Travel miles.",
            }
        )
    return warnings


def plan_trip(
    driver_name: str,
    origin: dict[str, Any],
    destination: dict[str, Any],
    departure_utc: datetime,
    timezone_name: str,
    load_lb: float,
    interval_mi: float,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now_utc = now_utc or datetime.now(UTC)
    driver = driver_name.strip() or "Driver"
    geometries, route_note = get_route_options(
        (origin["lat"], origin["lon"]),
        (destination["lat"], destination["lon"]),
        departure_utc,
        load_lb,
    )
    routes = [
        _build_route(route_id, geometry, departure_utc, interval_mi)
        for route_id, geometry in zip(ROUTE_IDS, geometries)
    ]
    weather_problem = _attach_weather(routes, load_lb, now_utc)

    summaries_by_id = {
        route["id"]: summarize_route(
            route["id"],
            route["duration_s"],
            [
                (checkpoint["covered_mi"], checkpoint["level_value"])
                for checkpoint in route["checkpoints"]
            ],
        )
        for route in routes
    }
    ranked = rank_routes(summaries_by_id.values())
    recommended_id = ranked[0].route_id
    reason = recommendation_reason(ranked[0], ranked[1] if len(ranked) > 1 else None)
    rank_by_id = {
        summary.route_id: position + 1 for position, summary in enumerate(ranked)
    }
    routes_by_id = {route["id"]: route for route in routes}
    warnings = _build_warnings(
        driver,
        routes_by_id,
        summaries_by_id,
        recommended_id,
        timezone_name,
        load_lb,
        route_note,
        weather_problem,
    )
    corridor_grid = [
        list(point) for point in build_grid([route["points"] for route in routes])
    ]

    # Turn the internal values into what the frontend gets (JSON friendly).
    for route in routes:
        summary = summaries_by_id[route["id"]]
        route["summary"] = {
            "no_travel_mi": round(summary.no_travel_mi, 1),
            "severe_mi": round(summary.severe_mi, 1),
            "high_mi": round(summary.high_mi, 1),
            "unknown_mi": round(summary.unknown_mi, 1),
            "avg_risk": (
                None if summary.avg_risk is None else round(summary.avg_risk, 2)
            ),
            "rank": rank_by_id[route["id"]],
        }
        del route["points"]
        for checkpoint in route["checkpoints"]:
            checkpoint["eta"] = to_iso(checkpoint["eta"])
            checkpoint["covered_mi"] = round(checkpoint["covered_mi"], 2)
            del checkpoint["level_value"]

    return {
        "driver_name": driver,
        "timezone": timezone_name,
        "departure": to_iso(departure_utc),
        "recommended_route_id": recommended_id,
        "reason": reason,
        "warnings": warnings,
        "corridor_grid": corridor_grid,
        "routes": routes,
    }
