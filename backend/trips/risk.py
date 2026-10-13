"""Weather risk rules from the assessment brief. Pure Python, no Django."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum


# IntEnum members are ints, so max() and comparisons work: NO_TRAVEL > SEVERE.
class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


# Machine names, sent to the frontend in the API response.
LEVEL_KEYS = {
    RiskLevel.LOW: "low",
    RiskLevel.MODERATE: "moderate",
    RiskLevel.HIGH: "high",
    RiskLevel.SEVERE: "severe",
    RiskLevel.NO_TRAVEL: "no_travel",
}

# Human names, used in warning text.
LEVEL_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}


# frozen=True makes the object read-only after it is created.
@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float | None
    # Inches in the hour.
    rain_in: float
    # Inches in the hour.
    snow_in: float


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    # Why the level was chosen, e.g. ("wind", "load").
    reasons: tuple[str, ...]


def effective_wind(sample: WeatherSample) -> float:
    """Gusts are what push trucks over, so use them, but never below sustained wind."""
    return max(sample.wind_mph, sample.gust_mph or 0.0)


def classify_wind(wind_mph: float) -> RiskLevel:
    if wind_mph < 25:
        return RiskLevel.LOW
    if wind_mph < 35:
        return RiskLevel.MODERATE
    if wind_mph < 45:
        return RiskLevel.HIGH
    if wind_mph < 55:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(rain_in: float) -> RiskLevel:
    if rain_in < 0.10:
        return RiskLevel.LOW
    if rain_in < 0.25:
        return RiskLevel.MODERATE
    if rain_in < 0.50:
        return RiskLevel.HIGH
    if rain_in <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_snow(snow_in: float) -> RiskLevel:
    if snow_in < 0.5:
        return RiskLevel.LOW
    if snow_in < 1.0:
        return RiskLevel.MODERATE
    if snow_in < 2.0:
        return RiskLevel.HIGH
    if snow_in <= 3.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def load_rule_level(wind_mph: float, load_lb: float) -> RiskLevel | None:
    """Heavier loads make strong wind worse. Returns the raised level, if any."""
    if 45 <= wind_mph < 55 and load_lb > 30000:
        return RiskLevel.NO_TRAVEL
    if 35 <= wind_mph < 45 and load_lb > 40000:
        return RiskLevel.SEVERE
    return None


def assess(sample: WeatherSample, load_lb: float) -> RiskAssessment:
    wind_mph = effective_wind(sample)
    factor_levels = {
        "wind": classify_wind(wind_mph),
        "rain": classify_rain(sample.rain_in),
        "snow": classify_snow(sample.snow_in),
    }
    # The checkpoint level is the worst of the three factors.
    level = max(factor_levels.values())
    reasons = tuple(
        factor
        for factor, factor_level in factor_levels.items()
        if factor_level == level and level > RiskLevel.LOW
    )
    # The load rules can only raise the level, never lower it.
    raised_level = load_rule_level(wind_mph, load_lb)
    if raised_level is not None and raised_level > level:
        return RiskAssessment(raised_level, ("wind", "load"))
    return RiskAssessment(level, reasons)


@dataclass(frozen=True)
class RouteRiskSummary:
    route_id: str
    duration_s: float
    no_travel_mi: float
    severe_mi: float
    high_mi: float
    unknown_mi: float
    # None when no checkpoint has a forecast.
    avg_risk: float | None


def summarize_route(
    route_id: str,
    duration_s: float,
    segments: Iterable[tuple[float, RiskLevel | None]],
) -> RouteRiskSummary:
    """segments: (covered_miles, RiskLevel or None for unknown) per checkpoint."""
    miles_by_level = {level: 0.0 for level in RiskLevel}
    unknown_mi = 0.0
    for covered_mi, level in segments:
        if level is None:
            unknown_mi += covered_mi
        else:
            miles_by_level[level] += covered_mi
    known_mi = sum(miles_by_level.values())
    avg_risk = None
    if known_mi > 0:
        # Average risk score, weighted by the miles each checkpoint covers.
        avg_risk = (
            sum(level * miles for level, miles in miles_by_level.items()) / known_mi
        )
    return RouteRiskSummary(
        route_id=route_id,
        duration_s=duration_s,
        no_travel_mi=miles_by_level[RiskLevel.NO_TRAVEL],
        severe_mi=miles_by_level[RiskLevel.SEVERE],
        high_mi=miles_by_level[RiskLevel.HIGH],
        unknown_mi=unknown_mi,
        avg_risk=avg_risk,
    )


def ranking_key(summary: RouteRiskSummary) -> tuple[float, float, float, float, float]:
    """The brief's priority order, with No Travel miles put first."""
    # A route with no forecast at all sorts after any route with a known average.
    avg_risk = math.inf if summary.avg_risk is None else round(summary.avg_risk, 3)
    return (
        round(summary.no_travel_mi, 1),
        round(summary.severe_mi, 1),
        round(summary.high_mi, 1),
        avg_risk,
        round(summary.duration_s),
    )


def rank_routes(summaries: Iterable[RouteRiskSummary]) -> list[RouteRiskSummary]:
    # Python compares tuples item by item, so the key order is the priority order.
    return sorted(summaries, key=ranking_key)


def format_duration(seconds: float) -> str:
    total_minutes = round(seconds / 60)
    return f"{total_minutes // 60}h {total_minutes % 60:02d}m"


# One label per item of ranking_key, in the same order.
REASON_LABELS = (
    "No Travel miles",
    "Severe miles",
    "High miles",
    "average risk",
    "travel time",
)


def _format_reason_value(label: str, reason_value: float) -> str:
    if label == "travel time":
        return format_duration(reason_value)
    if label == "average risk":
        # 3 decimals, the same precision the ranking uses, so a real difference is never hidden.
        return "n/a" if reason_value == math.inf else f"{reason_value:.3f}"
    return f"{reason_value:.0f}"


def recommendation_reason(
    best: RouteRiskSummary, runner_up: RouteRiskSummary | None
) -> str:
    if runner_up is None:
        return "It is the only route found."
    # Compare on the first criterion where the two routes differ.
    for label, best_value, other_value in zip(
        REASON_LABELS, ranking_key(best), ranking_key(runner_up)
    ):
        if best_value != other_value:
            return (
                f"{_format_reason_value(label, best_value)} {label} vs "
                f"{_format_reason_value(label, other_value)} on route {runner_up.route_id}."
            )
    return f"Ties with route {runner_up.route_id} on risk and time."
