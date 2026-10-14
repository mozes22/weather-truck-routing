import type { Weather } from './api';

// Shows a UTC time in a given time zone, e.g. "Tue, 02:00 PM CDT". Same 12 hour style as the
// departure field in the form.
export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  }).format(new Date(iso));
}

// 91800 seconds becomes "25h 30m".
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${minutes}m`;
}

export const formatMiles = (miles: number) => `${Math.round(miles).toLocaleString('en-US')} mi`;

// One line for popups and the timeline, e.g. "Wind 18 mph (gusts 25), rain 0 in, snow 0 in".
export function describeWeather(weather: Weather | null): string {
  if (!weather) {
    return 'No forecast for this time';
  }
  const gusts = weather.gust_mph === null ? '' : ` (gusts ${Math.round(weather.gust_mph)})`;
  return `Wind ${Math.round(weather.wind_mph)} mph${gusts}, rain ${weather.rain_in} in, snow ${weather.snow_in} in`;
}
