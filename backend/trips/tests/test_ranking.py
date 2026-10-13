from django.test import SimpleTestCase

from trips.risk import RiskLevel, rank_routes, recommendation_reason, summarize_route


def make_summary(
    route_id, hours=10.0, low=100.0, high=0.0, severe=0.0, no_travel=0.0, unknown=0.0
):
    segments = [
        (low, RiskLevel.LOW),
        (high, RiskLevel.HIGH),
        (severe, RiskLevel.SEVERE),
        (no_travel, RiskLevel.NO_TRAVEL),
        (unknown, None),
    ]
    return summarize_route(route_id, hours * 3600, segments)


class SummarizeTests(SimpleTestCase):
    def test_miles_and_weighted_average(self):
        summary = make_summary("A", low=75, high=25, unknown=10)
        self.assertEqual(summary.high_mi, 25)
        self.assertEqual(summary.unknown_mi, 10)
        # avg_risk can be None, so check that first. It also narrows the type for the next line.
        assert summary.avg_risk is not None
        self.assertAlmostEqual(summary.avg_risk, 0.5)

    def test_all_unknown_has_no_average(self):
        self.assertIsNone(make_summary("A", low=0, unknown=50).avg_risk)


class RankTests(SimpleTestCase):
    def ids(self, summaries):
        return [summary.route_id for summary in rank_routes(summaries)]

    def test_no_travel_ranks_last_even_if_fastest(self):
        self.assertEqual(
            self.ids(
                [
                    make_summary("A", hours=5, no_travel=1),
                    make_summary("B", hours=9, severe=50),
                ]
            ),
            ["B", "A"],
        )

    def test_fewer_severe_miles_wins(self):
        self.assertEqual(
            self.ids(
                [make_summary("A", severe=38), make_summary("B", hours=12, high=80)]
            ),
            ["B", "A"],
        )

    def test_fewer_high_miles_wins_when_severe_equal(self):
        self.assertEqual(
            self.ids(
                [make_summary("A", high=30), make_summary("B", high=10, hours=12)]
            ),
            ["B", "A"],
        )

    def test_lower_average_risk_wins_when_high_equal(self):
        moderate_heavy = summarize_route("A", 36000, [(100, RiskLevel.MODERATE)])
        calm = summarize_route("B", 40000, [(100, RiskLevel.LOW)])
        self.assertEqual(self.ids([moderate_heavy, calm]), ["B", "A"])

    def test_shortest_time_breaks_full_tie(self):
        self.assertEqual(
            self.ids([make_summary("A", hours=11), make_summary("B", hours=10)]),
            ["B", "A"],
        )

    def test_known_risk_beats_all_unknown(self):
        self.assertEqual(
            self.ids(
                [make_summary("A", low=0, unknown=100), make_summary("B", hours=12)]
            ),
            ["B", "A"],
        )


class ReasonTests(SimpleTestCase):
    def test_reason_names_first_differing_criterion(self):
        self.assertEqual(
            recommendation_reason(make_summary("A"), make_summary("B", severe=38)),
            "0 Severe miles vs 38 on route B.",
        )

    def test_reason_for_time(self):
        self.assertEqual(
            recommendation_reason(
                make_summary("A", hours=15.5), make_summary("B", hours=17)
            ),
            "15h 30m travel time vs 17h 00m on route B.",
        )

    def test_reason_single_route(self):
        self.assertEqual(
            recommendation_reason(make_summary("A"), None),
            "It is the only route found.",
        )
