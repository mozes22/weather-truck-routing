"""Small builders for fake routes and forecasts used across tests."""

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
