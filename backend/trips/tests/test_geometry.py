from django.test import SimpleTestCase

from trips.geometry import (
    bearing_deg,
    covered_miles,
    cumulative_miles,
    haversine_mi,
    interpolate,
    offset_point,
    point_at_mile,
    sample_miles,
)


class GeometryTests(SimpleTestCase):
    def test_one_degree_latitude_is_about_69_miles(self):
        self.assertAlmostEqual(haversine_mi((0, 0), (1, 0)), 69.09, delta=0.1)

    def test_cumulative_miles(self):
        totals = cumulative_miles([(0, 0), (1, 0), (2, 0)])
        self.assertEqual(totals[0], 0)
        self.assertAlmostEqual(totals[2], 138.18, delta=0.2)

    def test_interpolate_clamps_and_blends(self):
        self.assertEqual(interpolate([0, 10], [100, 200], -5), 100)
        self.assertEqual(interpolate([0, 10], [100, 200], 15), 200)
        self.assertEqual(interpolate([0, 10], [100, 200], 2.5), 125)

    def test_point_at_mile_halfway(self):
        points = [(0.0, 0.0), (2.0, 0.0)]
        cumulative = cumulative_miles(points)
        latitude, longitude = point_at_mile(points, cumulative, cumulative[-1] / 2)
        self.assertAlmostEqual(latitude, 1.0, places=3)
        self.assertAlmostEqual(longitude, 0.0, places=6)

    def test_sample_miles_includes_both_ends(self):
        self.assertEqual(sample_miles(60, 25), [0, 25, 50, 60])
        self.assertEqual(sample_miles(50, 25), [0, 25, 50])

    def test_covered_miles_add_up_to_route_length(self):
        covered = covered_miles([0, 25, 50, 60])
        self.assertEqual(covered, [12.5, 25.0, 17.5, 5.0])
        self.assertAlmostEqual(sum(covered), 60)

    def test_bearing_east_and_offset_north(self):
        self.assertAlmostEqual(bearing_deg((0, 0), (0, 1)), 90, delta=0.01)
        latitude, longitude = offset_point((0, 0), 0, 69.09)
        self.assertAlmostEqual(latitude, 1.0, delta=0.01)
        self.assertAlmostEqual(longitude, 0.0, delta=0.001)
