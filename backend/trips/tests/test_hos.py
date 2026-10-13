from django.test import SimpleTestCase

from trips.hos import elapsed_seconds, plan_stops

HOUR = 3600


class PlanStopsTests(SimpleTestCase):
    def kinds_and_hours(self, total_hours):
        return [
            (stop.kind, stop.driving_s_at / HOUR)
            for stop in plan_stops(total_hours * HOUR)
        ]

    def test_short_trip_has_no_stops(self):
        self.assertEqual(self.kinds_and_hours(7), [])

    def test_break_after_eight_hours(self):
        self.assertEqual(self.kinds_and_hours(9), [("break", 8)])

    def test_exactly_eleven_hours_needs_only_the_break(self):
        self.assertEqual(self.kinds_and_hours(11), [("break", 8)])

    def test_rest_after_eleven_hours(self):
        self.assertEqual(self.kinds_and_hours(12), [("break", 8), ("rest", 11)])

    def test_two_shifts(self):
        self.assertEqual(
            self.kinds_and_hours(25),
            [("break", 8), ("rest", 11), ("break", 19), ("rest", 22)],
        )


class ElapsedTests(SimpleTestCase):
    def test_elapsed_adds_stops_already_taken(self):
        stops = plan_stops(12 * HOUR)
        self.assertEqual(elapsed_seconds(7 * HOUR, stops), 7 * HOUR)
        self.assertEqual(elapsed_seconds(9 * HOUR, stops), 9.5 * HOUR)
        self.assertEqual(elapsed_seconds(12 * HOUR, stops), 22.5 * HOUR)
