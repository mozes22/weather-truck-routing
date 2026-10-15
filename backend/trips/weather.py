"""Open-Meteo hourly forecasts for many points at once, cached."""

import math
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from django.core.cache import cache

from trips.geometry import Point
from trips.risk import WeatherSample

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
# Open-Meteo accepts many locations per request. We send them in small groups, side by side.
# On Cloud Run a request for 90 locations hung until the timeout, while 30 answered in about a second.
BATCH_SIZE = 30
MAX_PARALLEL_BATCHES = 4
CACHE_SECONDS = 30 * 60
# Open-Meteo forecasts at most 16 days ahead.
MAX_FORECAST_DAYS = 16
# A small batch answers in a second or two, so a hung request is given up on quickly.
REQUEST_TIMEOUT_S = 30
# One try plus one retry. Open-Meteo sometimes answers 503 or hangs, and a second try usually works.
MAX_ATTEMPTS = 2
RETRY_DELAY_S = 1
# "Try again later" answers are retried. Others, such as 429 (rate limit), are not.
RETRY_STATUS_CODES = (502, 503, 504)


class WeatherUnavailable(Exception):
    """The forecast could not be fetched (network error, rate limit, bad response)."""


@dataclass
class HourlySeries:
    """The hourly forecast for one location. Each list has one entry per hour."""

    start_utc: datetime
    wind_mph: list
    gust_mph: list
    rain_in: list
    showers_in: list
    snow_in: list


def round_coord(lat: float, lon: float) -> Point:
    """Round to 0.1 degree (about 11 km). Nearby checkpoints share one forecast and one cache entry."""
    return (round(lat, 1), round(lon, 1))


def _cache_key(coord: Point, forecast_days: int) -> str:
    return f"weather:{coord[0]:.1f}:{coord[1]:.1f}:{forecast_days}"


def _get_with_retry(params: dict) -> requests.Response:
    """Call Open-Meteo, trying once more after a network error or a temporary server error."""
    for attempt in range(MAX_ATTEMPTS):
        is_last_attempt = attempt == MAX_ATTEMPTS - 1
        try:
            response = requests.get(
                OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT_S
            )
        except requests.RequestException as error:
            if is_last_attempt:
                # Only the error type is shown to the driver, not the technical details.
                raise WeatherUnavailable(
                    f"Weather service did not respond ({type(error).__name__})."
                ) from None
            time.sleep(RETRY_DELAY_S)
            continue
        if response.status_code in RETRY_STATUS_CODES and not is_last_attempt:
            time.sleep(RETRY_DELAY_S)
            continue
        return response
    # The loop always returns or raises. This line only keeps the type checker happy.
    raise WeatherUnavailable("Weather service did not respond.")


def _request_batch(coords: list[Point], forecast_days: int) -> list[dict]:
    """One HTTP call for a group of locations. Returns one payload per location."""
    params = {
        "latitude": ",".join(f"{lat:.1f}" for lat, _ in coords),
        "longitude": ",".join(f"{lon:.1f}" for _, lon in coords),
        "hourly": HOURLY_FIELDS,
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "forecast_days": forecast_days,
    }
    response = _get_with_retry(params)
    if response.status_code != 200:
        raise WeatherUnavailable(f"Weather service returned {response.status_code}")
    payload = response.json()
    # A request for a single location returns a dict, many locations return a list.
    return payload if isinstance(payload, list) else [payload]


def _parse_series(location_payload: dict) -> HourlySeries:
    hourly = location_payload["hourly"]
    return HourlySeries(
        start_utc=datetime.fromisoformat(hourly["time"][0]).replace(tzinfo=UTC),
        wind_mph=hourly["wind_speed_10m"],
        gust_mph=hourly["wind_gusts_10m"],
        rain_in=hourly["rain"],
        showers_in=hourly["showers"],
        snow_in=hourly["snowfall"],
    )


def forecast_days_until(last_moment_utc: datetime, now_utc: datetime) -> int:
    """How many forecast days to ask for so the forecast reaches the given moment."""
    # Open-Meteo counts days from midnight today at the location, so one extra day covers
    # the hours already passed today.
    days = math.ceil((last_moment_utc - now_utc).total_seconds() / 86400) + 1
    return max(1, min(MAX_FORECAST_DAYS, days))


def fetch_series(coords, forecast_days: int) -> dict[Point, HourlySeries]:
    """Forecast for every location, keyed by the rounded coordinate. Uses the cache first."""
    # dict.fromkeys removes duplicates and keeps the order.
    unique_coords = list(dict.fromkeys(round_coord(lat, lon) for lat, lon in coords))
    series_by_coord = {}
    missing_coords = []
    for coord in unique_coords:
        cached_series = cache.get(_cache_key(coord, forecast_days))
        if cached_series is None:
            missing_coords.append(coord)
        else:
            series_by_coord[coord] = cached_series
    batches = [
        missing_coords[batch_start : batch_start + BATCH_SIZE]
        for batch_start in range(0, len(missing_coords), BATCH_SIZE)
    ]
    if not batches:
        return series_by_coord
    # The batches are sent side by side. If one fails, the error reaches the caller as before.
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as pool:
        payloads_per_batch = list(
            pool.map(lambda batch: _request_batch(batch, forecast_days), batches)
        )
    for batch, payloads in zip(batches, payloads_per_batch):
        for coord, location_payload in zip(batch, payloads):
            series = _parse_series(location_payload)
            series_by_coord[coord] = series
            cache.set(_cache_key(coord, forecast_days), series, CACHE_SECONDS)
    return series_by_coord


def sample_at(series: HourlySeries, when_utc: datetime) -> WeatherSample | None:
    """Weather for the hour the truck is in, or None if that time is outside the forecast.

    Open-Meteo stamps each value at the end of its hour, so a 10:20 arrival uses the 11:00 value.
    """
    hours_from_start = (when_utc - series.start_utc).total_seconds() / 3600
    # The tiny 1e-9 keeps an arrival exactly on the hour in that hour.
    hour_index = math.ceil(hours_from_start - 1e-9)
    if hour_index < 0 or hour_index >= len(series.wind_mph):
        return None
    wind_mph = series.wind_mph[hour_index]
    rain_in = series.rain_in[hour_index]
    snow_in = series.snow_in[hour_index]
    # Open-Meteo sometimes returns null for an hour. Treat that as no forecast.
    if wind_mph is None or rain_in is None or snow_in is None:
        return None
    return WeatherSample(
        wind_mph=wind_mph,
        gust_mph=series.gust_mph[hour_index],
        # Rain for the risk rules is rain plus showers.
        rain_in=rain_in + (series.showers_in[hour_index] or 0.0),
        snow_in=snow_in,
    )
