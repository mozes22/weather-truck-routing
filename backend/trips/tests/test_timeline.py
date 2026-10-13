from django.test import SimpleTestCase

from trips.timeline import cumulative_driving_seconds


class DrivingSecondsTests(SimpleTestCase):
    def test_spreads_each_span_by_distance(self):
        seconds = cumulative_driving_seconds(
            [0, 10, 20, 30, 40], [0, 2], [1000, 3000], 4000
        )
        self.assertEqual(seconds, [0, 500, 1000, 2500, 4000])

    def test_falls_back_to_even_speed_without_spans(self):
        self.assertEqual(
            cumulative_driving_seconds([0, 10, 40], [], [], 400), [0, 100, 400]
        )
