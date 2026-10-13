export type RiskLabel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel' | 'unknown';

export interface Place {
  label: string;
  lat: number;
  lon: number;
}

export interface Weather {
  wind_mph: number;
  gust_mph: number | null;
  effective_wind_mph: number;
  rain_in: number;
  snow_in: number;
}

export interface Checkpoint {
  mile: number;
  lat: number;
  lon: number;
  eta: string;
  level: RiskLabel;
  reasons: string[];
  weather: Weather | null;
  covered_mi: number;
}

export interface Stop {
  kind: 'break' | 'rest';
  mile: number;
  lat: number;
  lon: number;
  start: string;
  duration_min: number;
}

export interface RouteSummary {
  no_travel_mi: number;
  severe_mi: number;
  high_mi: number;
  unknown_mi: number;
  avg_risk: number | null;
  rank: number;
}

export interface RouteOption {
  id: string;
  distance_mi: number;
  driving_s: number;
  duration_s: number;
  arrival: string;
  // Points of the line to draw, as [longitude, latitude].
  coordinates: [number, number][];
  checkpoints: Checkpoint[];
  stops: Stop[];
  summary: RouteSummary;
}

export interface TripWarning {
  severity: 'error' | 'warning' | 'info' | 'success';
  message: string;
}

export interface PlanResponse {
  driver_name: string;
  timezone: string;
  departure: string;
  recommended_route_id: string;
  reason: string;
  warnings: TripWarning[];
  // Points around the routes, sent back to the server to get the heatmap.
  corridor_grid: [number, number][];
  routes: RouteOption[];
}

export interface PlanRequest {
  driver_name: string;
  origin: Place;
  destination: Place;
  departure: string;
  load_lb: number;
  interval_mi: 10 | 25 | 50;
}

export interface CorridorForecast {
  start: string;
  // Points as [longitude, latitude]. Each hour array has one value per point.
  points: [number, number][];
  risk: (number | null)[][];
  wind: (number | null)[][];
  rain: (number | null)[][];
  snow: (number | null)[][];
}

// An error with a message for the whole form and optional messages per field.
export class ApiError extends Error {
  fieldErrors: Record<string, string>;

  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.fieldErrors = fieldErrors;
  }
}

// Django answers 400 with {"field": ["message"]}. Turn that into {field: "message"}.
function toFieldErrors(body: Record<string, unknown>): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  for (const [field, messages] of Object.entries(body)) {
    fieldErrors[field] = Array.isArray(messages) ? messages.join(' ') : 'Invalid value.';
  }
  return fieldErrors;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // 422 and 502 come with {"detail": "..."}.
    if (body && typeof body.detail === 'string') {
      throw new ApiError(body.detail);
    }
    if (body && typeof body === 'object') {
      throw new ApiError('Please check the highlighted fields.', toFieldErrors(body));
    }
    throw new ApiError(`Request failed (${response.status}).`);
  }
  return body as T;
}

export const searchPlaces = (query: string, signal: AbortSignal) =>
  request<Place[]>(`/api/geocode?q=${encodeURIComponent(query)}`, { signal });

export const planTrip = (planRequest: PlanRequest) =>
  request<PlanResponse>('/api/plan', { method: 'POST', body: JSON.stringify(planRequest) });

export const fetchCorridorForecast = (points: [number, number][], loadLb: number) =>
  request<CorridorForecast>('/api/corridor-forecast', {
    method: 'POST',
    body: JSON.stringify({ points, load_lb: loadLb }),
  });
