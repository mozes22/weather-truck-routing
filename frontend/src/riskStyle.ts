import type { RiskLabel } from './api';

export const RISK_COLORS: Record<RiskLabel, string> = {
  low: '#2e7d32',
  moderate: '#f9a825',
  high: '#ef6c00',
  severe: '#c62828',
  no_travel: '#212121',
  unknown: '#9e9e9e',
};

export const RISK_LABELS: Record<RiskLabel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
  unknown: 'No forecast',
};

// Chip colours for a risk level. Light backgrounds (yellow, grey) need dark text to stay readable.
export function riskChipSx(level: RiskLabel) {
  const hasLightBackground = level === 'moderate' || level === 'unknown';
  return { bgcolor: RISK_COLORS[level], color: hasLightBackground ? '#212121' : '#ffffff' };
}

// Blue, teal and brown: distinct from each other and from the risk colours.
export const ROUTE_COLORS: Record<string, string> = { A: '#1565c0', B: '#00838f', C: '#6d4c41' };
