import type { FeatureCollection } from 'geojson';
import type { LayerProps } from 'react-map-gl/maplibre';
import type { CorridorForecast } from './api';

export type HeatLayerKey = 'risk' | 'wind' | 'rain' | 'snow';

export const HEAT_LAYER_KEYS: HeatLayerKey[] = ['risk', 'wind', 'rain', 'snow'];

interface HeatLayerInfo {
  label: string;
  // The value that gets the strongest colour. Higher values are capped to it.
  maxValue: number;
  // Text under the left and right end of the colour bar.
  lowLabel: string;
  highLabel: string;
}

export const HEAT_LAYERS: Record<HeatLayerKey, HeatLayerInfo> = {
  risk: { label: 'Risk', maxValue: 4, lowLabel: 'Low', highLabel: 'No Travel' },
  wind: { label: 'Wind', maxValue: 60, lowLabel: '0 mph', highLabel: '60+ mph' },
  rain: { label: 'Rain', maxValue: 1, lowLabel: '0 in/hr', highLabel: '1+ in/hr' },
  snow: { label: 'Snow', maxValue: 3, lowLabel: '0 in/hr', highLabel: '3+ in/hr' },
};

// Green, yellow, orange, red, purple. The map layer and the legend bar share these.
export const HEAT_COLORS = ['#2e7d32', '#f9a825', '#ef6c00', '#c62828', '#6a1b9a'];

// The same style for every layer. Only the point weights change.
// It is added under the route lines (beforeId in RouteMap), so routes stay visible.
export const HEATMAP_LAYER: LayerProps = {
  id: 'corridor-heat',
  type: 'heatmap',
  paint: {
    'heatmap-weight': ['get', 'weight'],
    'heatmap-intensity': 1,
    // Bigger blobs when zoomed in, so neighbouring points still blend into one area.
    'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 16, 9, 70],
    'heatmap-opacity': 0.75,
    'heatmap-color': [
      'interpolate',
      ['linear'],
      ['heatmap-density'],
      0,
      'rgba(0, 0, 0, 0)',
      0.2,
      HEAT_COLORS[0],
      0.4,
      HEAT_COLORS[1],
      0.6,
      HEAT_COLORS[2],
      0.8,
      HEAT_COLORS[3],
      1,
      HEAT_COLORS[4],
    ],
  },
};

// One hour of one layer as map points. Missing and zero values are left out.
export function heatDataFor(
  forecast: CorridorForecast,
  layerKey: HeatLayerKey,
  hour: number,
): FeatureCollection {
  const values = forecast[layerKey][hour] ?? [];
  const { maxValue } = HEAT_LAYERS[layerKey];
  const features: FeatureCollection['features'] = [];
  for (let pointIndex = 0; pointIndex < values.length; pointIndex += 1) {
    const value = values[pointIndex];
    if (value !== null && value > 0) {
      features.push({
        type: 'Feature',
        properties: { weight: Math.min(value / maxValue, 1) },
        geometry: { type: 'Point', coordinates: forecast.points[pointIndex] },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}
