"""Weather risk rules from the assessment brief. Pure Python, no Django."""

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
