"""Simplified FMCSA Hours-of-Service: when the driver has to stop."""

from dataclasses import dataclass

HOUR = 3600
# A 30 minute break is due after 8 hours of driving.
DRIVING_BEFORE_BREAK_S = 8 * HOUR
BREAK_S = 30 * 60
# A 10 hour rest is due after 11 hours of driving. Then the counters reset.
DRIVING_PER_SHIFT_S = 11 * HOUR
REST_S = 10 * HOUR


@dataclass(frozen=True)
class Stop:
    # "break" or "rest".
    kind: str
    # Driving time on the clock when the stop starts.
    driving_s_at: float
    duration_s: float


def plan_stops(total_driving_s: float) -> list[Stop]:
    """One 30 min break after 8 h and a 10 h rest after 11 h, every shift.

    The 14 h on-duty window is not modelled.
    """
    stops: list[Stop] = []
    shift_start_s = 0.0
    while True:
        break_at = shift_start_s + DRIVING_BEFORE_BREAK_S
        if break_at < total_driving_s:
            stops.append(Stop("break", break_at, BREAK_S))
        rest_at = shift_start_s + DRIVING_PER_SHIFT_S
        # No rest needed if the trip ends before (or exactly at) the shift limit.
        if rest_at >= total_driving_s:
            return stops
        stops.append(Stop("rest", rest_at, REST_S))
        shift_start_s = rest_at


def elapsed_seconds(driving_s: float, stops: list[Stop]) -> float:
    """Clock time since departure once the truck has driven driving_s seconds."""
    return driving_s + sum(
        stop.duration_s for stop in stops if stop.driving_s_at < driving_s
    )
