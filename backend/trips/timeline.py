"""Driving time at every point of a route, from HERE span durations."""


def cumulative_driving_seconds(
    cumulative_mi: list[float],
    span_offsets: list[int],
    span_durations_s: list[float],
    total_duration_s: float,
) -> list[float]:
    """Spread each span's duration over its points in proportion to distance.

    span_offsets[k] is the index of the first point of span k. Without spans
    (or with zero durations) we assume an even speed over the whole route.
    """
    point_count = len(cumulative_mi)
    total_miles = cumulative_mi[-1]
    if total_miles == 0:
        return [0.0] * point_count
    if not span_offsets or sum(span_durations_s) <= 0:
        return [total_duration_s * mile / total_miles for mile in cumulative_mi]

    seconds = [0.0] * point_count
    # Each span runs from its first point to the first point of the next span.
    boundaries = list(span_offsets) + [point_count - 1]
    elapsed_s = 0.0
    for span_index, span_duration_s in enumerate(span_durations_s):
        first_point = boundaries[span_index]
        last_point = boundaries[span_index + 1]
        span_miles = cumulative_mi[last_point] - cumulative_mi[first_point]
        for point_index in range(first_point + 1, last_point + 1):
            # Share of this span's miles driven by the time we reach the point.
            share = (
                1.0
                if span_miles == 0
                else (cumulative_mi[point_index] - cumulative_mi[first_point])
                / span_miles
            )
            seconds[point_index] = elapsed_s + span_duration_s * share
        elapsed_s += span_duration_s
    return seconds
