"""Distance and position helpers. Points are (lat, lon) in degrees."""

import bisect
import math

# Mean radius of the Earth in miles.
EARTH_RADIUS_MI = 3958.8

# A point on the map: (latitude, longitude).
Point = tuple[float, float]


def haversine_mi(start: Point, end: Point) -> float:
    """Straight-line distance over the Earth's surface between two points, in miles."""
    start_lat, start_lon = map(math.radians, start)
    end_lat, end_lon = map(math.radians, end)
    delta_lat = end_lat - start_lat
    delta_lon = end_lon - start_lon
    half_chord = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(start_lat) * math.cos(end_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(half_chord))


def cumulative_miles(points: list[Point]) -> list[float]:
    """Miles from the first point to each point along the route. Starts at 0."""
    totals = [0.0]
    for previous_point, current_point in zip(points, points[1:]):
        totals.append(totals[-1] + haversine_mi(previous_point, current_point))
    return totals


def _locate(sorted_values: list[float], target: float) -> tuple[int, float]:
    """Segment index and fraction along it for a target inside sorted_values."""
    # Binary search for the segment that contains the target.
    segment_index = bisect.bisect_right(sorted_values, target) - 1
    segment_index = max(0, min(segment_index, len(sorted_values) - 2))
    segment_length = sorted_values[segment_index + 1] - sorted_values[segment_index]
    if segment_length == 0:
        return segment_index, 0.0
    return segment_index, (target - sorted_values[segment_index]) / segment_length


def interpolate(xs: list[float], ys: list[float], x: float) -> float:
    """The y value at x, blended between the two nearest known points. Clamped at both ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    segment_index, fraction = _locate(xs, x)
    return ys[segment_index] + (ys[segment_index + 1] - ys[segment_index]) * fraction


def point_at_mile(points: list[Point], cumulative: list[float], mile: float) -> Point:
    """The map point that lies `mile` miles along the route."""
    if mile <= 0:
        return points[0]
    if mile >= cumulative[-1]:
        return points[-1]
    segment_index, fraction = _locate(cumulative, mile)
    start_lat, start_lon = points[segment_index]
    end_lat, end_lon = points[segment_index + 1]
    return (
        start_lat + (end_lat - start_lat) * fraction,
        start_lon + (end_lon - start_lon) * fraction,
    )


def sample_miles(total_mi: float, interval_mi: float) -> list[float]:
    """0, interval, 2*interval, ... and always the final mile."""
    miles: list[float] = []
    mile = 0.0
    # The 0.01 margin avoids a duplicate checkpoint right next to the end.
    while mile < total_mi - 0.01:
        miles.append(mile)
        mile += interval_mi
    miles.append(total_mi)
    return miles


def covered_miles(sample: list[float]) -> list[float]:
    """Each checkpoint covers half the gap to its neighbours, so the total equals the route length."""
    if len(sample) == 1:
        return [0.0]
    covered: list[float] = []
    last_index = len(sample) - 1
    for index, mile in enumerate(sample):
        start = sample[0] if index == 0 else (sample[index - 1] + mile) / 2
        end = sample[-1] if index == last_index else (mile + sample[index + 1]) / 2
        covered.append(end - start)
    return covered


def bearing_deg(start: Point, end: Point) -> float:
    """Compass direction from start to end: 0 is north, 90 is east."""
    start_lat, start_lon = map(math.radians, start)
    end_lat, end_lon = map(math.radians, end)
    delta_lon = end_lon - start_lon
    east = math.sin(delta_lon) * math.cos(end_lat)
    north = math.cos(start_lat) * math.sin(end_lat) - math.sin(start_lat) * math.cos(
        end_lat
    ) * math.cos(delta_lon)
    return (math.degrees(math.atan2(east, north)) + 360) % 360


def offset_point(origin: Point, bearing: float, distance_mi: float) -> Point:
    """The point distance_mi away from origin in the bearing direction."""
    origin_lat, origin_lon = map(math.radians, origin)
    bearing_rad = math.radians(bearing)
    # Distance as an angle on the Earth's surface.
    angular_distance = distance_mi / EARTH_RADIUS_MI
    target_lat = math.asin(
        math.sin(origin_lat) * math.cos(angular_distance)
        + math.cos(origin_lat) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    target_lon = origin_lon + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(origin_lat),
        math.cos(angular_distance) - math.sin(origin_lat) * math.sin(target_lat),
    )
    # Wrap the longitude into the -180 to 180 range.
    return (math.degrees(target_lat), (math.degrees(target_lon) + 540) % 360 - 180)


def downsample(
    points: list[Point], cumulative: list[float], step_mi: float
) -> list[Point]:
    """Keep a point roughly every step_mi, always keeping the first and last."""
    kept = [points[0]]
    last_kept_mile = 0.0
    for point, mile in zip(points[1:-1], cumulative[1:-1]):
        if mile - last_kept_mile >= step_mi:
            kept.append(point)
            last_kept_mile = mile
    if len(points) > 1:
        kept.append(points[-1])
    return kept
