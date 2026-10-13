from django.test import SimpleTestCase

from trips.risk import (
    RiskLevel,
    WeatherSample,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
)

LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def calm_sample(**overrides):
    fields = {"wind_mph": 5.0, "gust_mph": 8.0, "rain_in": 0.0, "snow_in": 0.0}
    fields.update(overrides)
    return WeatherSample(**fields)


class ThresholdTests(SimpleTestCase):
    def test_wind_boundaries(self):
        cases = [
            (0, LOW),
            (24.9, LOW),
            (25, MODERATE),
            (34.9, MODERATE),
            (35, HIGH),
            (44.9, HIGH),
            (45, SEVERE),
            (54.9, SEVERE),
            (55, NO_TRAVEL),
            (80, NO_TRAVEL),
        ]
        for wind_mph, expected_level in cases:
            with self.subTest(wind_mph=wind_mph):
                self.assertEqual(classify_wind(wind_mph), expected_level)

    def test_rain_boundaries(self):
        cases = [
            (0, LOW),
            (0.099, LOW),
            (0.10, MODERATE),
            (0.249, MODERATE),
            (0.25, HIGH),
            (0.499, HIGH),
            (0.50, SEVERE),
            (1.00, SEVERE),
            (1.01, NO_TRAVEL),
        ]
        for rain_in, expected_level in cases:
            with self.subTest(rain_in=rain_in):
                self.assertEqual(classify_rain(rain_in), expected_level)

    def test_snow_boundaries(self):
        cases = [
            (0, LOW),
            (0.49, LOW),
            (0.5, MODERATE),
            (1.0, HIGH),
            (1.99, HIGH),
            (2.0, SEVERE),
            (3.0, SEVERE),
            (3.01, NO_TRAVEL),
        ]
        for snow_in, expected_level in cases:
            with self.subTest(snow_in=snow_in):
                self.assertEqual(classify_snow(snow_in), expected_level)


class AssessTests(SimpleTestCase):
    def test_calm_weather_is_low_with_no_reasons(self):
        result = assess(calm_sample(), load_lb=20000)
        self.assertEqual((result.level, result.reasons), (LOW, ()))

    def test_uses_gust_when_higher_than_sustained(self):
        result = assess(calm_sample(wind_mph=10, gust_mph=47), load_lb=0)
        self.assertEqual((result.level, result.reasons), (SEVERE, ("wind",)))

    def test_missing_gust_falls_back_to_sustained(self):
        self.assertEqual(
            assess(calm_sample(wind_mph=36, gust_mph=None), load_lb=0).level, HIGH
        )

    def test_gust_lower_than_sustained_uses_sustained(self):
        self.assertEqual(
            assess(calm_sample(wind_mph=46, gust_mph=30), load_lb=0).level, SEVERE
        )

    def test_worst_factor_wins_and_ties_list_both(self):
        result = assess(calm_sample(rain_in=0.3, snow_in=1.5), load_lb=0)
        self.assertEqual((result.level, result.reasons), (HIGH, ("rain", "snow")))

    def test_load_rule_no_travel_above_30000(self):
        result = assess(calm_sample(gust_mph=47), load_lb=30001)
        self.assertEqual((result.level, result.reasons), (NO_TRAVEL, ("wind", "load")))

    def test_load_rule_not_applied_at_exactly_30000(self):
        self.assertEqual(assess(calm_sample(gust_mph=47), load_lb=30000).level, SEVERE)

    def test_load_rule_severe_above_40000(self):
        result = assess(calm_sample(gust_mph=40), load_lb=40001)
        self.assertEqual((result.level, result.reasons), (SEVERE, ("wind", "load")))

    def test_load_rule_not_applied_at_exactly_40000(self):
        self.assertEqual(assess(calm_sample(gust_mph=40), load_lb=40000).level, HIGH)

    def test_load_rule_never_lowers_level(self):
        result = assess(calm_sample(gust_mph=40, snow_in=3.5), load_lb=45000)
        self.assertEqual((result.level, result.reasons), (NO_TRAVEL, ("snow",)))

    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(assess(calm_sample(gust_mph=55), load_lb=0).level, NO_TRAVEL)
