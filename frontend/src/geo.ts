import type { RouteOption } from './api';

// A point on the map as [longitude, latitude], the order the map uses.
export type LonLat = [number, number];

const MS_PER_MINUTE = 60_000;
// Mean radius of the Earth in miles.
const EARTH_RADIUS_MILES = 3958.8;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

// Straight-line distance over the Earth's surface between two points, in miles.
export function haversineMiles(from: LonLat, to: LonLat): number {
  const deltaLatitude = toRadians(to[1] - from[1]);
  const deltaLongitude = toRadians(to[0] - from[0]);
  const halfChord =
    Math.sin(deltaLatitude / 2) ** 2 +
    Math.cos(toRadians(from[1])) * Math.cos(toRadians(to[1])) * Math.sin(deltaLongitude / 2) ** 2;
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.sqrt(halfChord));
}

// Miles from the first point to each point along the line. The first value is 0.
export function cumulativeMiles(points: LonLat[]): number[] {
  const totals = [0];
  for (let index = 1; index < points.length; index += 1) {
    totals.push(totals[index - 1] + haversineMiles(points[index - 1], points[index]));
  }
  return totals;
}

// The point that lies the given number of miles along the line.
export function pointAtMile(points: LonLat[], cumulative: number[], mile: number): LonLat {
  if (mile <= 0) {
    return points[0];
  }
  const lastIndex = points.length - 1;
  if (mile >= cumulative[lastIndex]) {
    return points[lastIndex];
  }
  // The first point at or beyond the wanted mile ends the segment that contains it.
  const endIndex = cumulative.findIndex((miles) => miles >= mile);
  const startIndex = endIndex - 1;
  const segmentMiles = cumulative[endIndex] - cumulative[startIndex];
  const fraction = segmentMiles === 0 ? 0 : (mile - cumulative[startIndex]) / segmentMiles;
  const start = points[startIndex];
  const end = points[endIndex];
  return [start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction];
}

interface TimeMark {
  timeMs: number;
  mile: number;
}

export interface TruckState {
  location: LonLat;
  // False while the truck waits at the origin before leaving or at the destination after arriving.
  onTheRoad: boolean;
}

// Where the truck is at a given time. Before it leaves it waits at the origin and after it
// arrives it stays at the destination. Null only when the route has no timing at all.
// `cumulative` holds the miles along route.coordinates, from cumulativeMiles.
export function truckPosition(
  route: RouteOption,
  cumulative: number[],
  timeMs: number,
): TruckState | null {
  // Known moments: every checkpoint arrival, and the start and end of every break or rest.
  // During a stop the mile stays the same, so the truck stands still.
  const stopMarks = route.stops.flatMap((stop) => {
    const startMs = Date.parse(stop.start);
    return [
      { timeMs: startMs, mile: stop.mile },
      { timeMs: startMs + stop.duration_min * MS_PER_MINUTE, mile: stop.mile },
    ];
  });
  const checkpointMarks = route.checkpoints.map((checkpoint) => ({
    timeMs: Date.parse(checkpoint.eta),
    mile: checkpoint.mile,
  }));
  const marks: TimeMark[] = [...checkpointMarks, ...stopMarks].sort((a, b) => a.timeMs - b.timeMs);

  if (marks.length === 0) {
    return null;
  }
  const firstMark = marks[0];
  const lastMark = marks[marks.length - 1];
  const onTheRoad = timeMs >= firstMark.timeMs && timeMs <= lastMark.timeMs;
  // Outside the trip, use the nearest end of it so the truck stays at the origin or destination.
  const clampedTimeMs = Math.min(Math.max(timeMs, firstMark.timeMs), lastMark.timeMs);

  // Blend the miles between the marks just before and just after the wanted time.
  const nextIndex = marks.findIndex((mark) => mark.timeMs >= clampedTimeMs);
  const nextMark = marks[nextIndex];
  const previousMark = marks[Math.max(nextIndex - 1, 0)];
  const gapMs = nextMark.timeMs - previousMark.timeMs;
  const fraction = gapMs === 0 ? 1 : (clampedTimeMs - previousMark.timeMs) / gapMs;
  const serverMile = previousMark.mile + (nextMark.mile - previousMark.mile) * fraction;

  // The server measures miles on the full route and the drawn line is simplified, so the two
  // totals differ slightly. Scale the mile to the drawn line so the truck ends where it ends.
  const drawnMiles = cumulative[cumulative.length - 1];
  const scale = lastMark.mile === 0 ? 1 : drawnMiles / lastMark.mile;
  return { location: pointAtMile(route.coordinates, cumulative, serverMile * scale), onTheRoad };
}
