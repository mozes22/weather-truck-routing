import LocalShippingIcon from '@mui/icons-material/LocalShipping';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { FeatureCollection } from 'geojson';
import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { useEffect, useMemo, useRef, useState } from 'react';
import MapView, {
  Layer,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type LayerProps,
  type MapLayerMouseEvent,
  type MapRef,
} from 'react-map-gl/maplibre';
import type { PlanResponse, RouteOption } from '../api';
import { describeWeather, formatTime } from '../format';
import type { LonLat } from '../geo';
import { HEATMAP_LAYER } from '../heatmap';
import { RISK_COLORS, RISK_LABELS, ROUTE_COLORS, riskChipSx } from '../riskStyle';

// MapLibre looks for its worker file next to its own script. Vite moves that script, so the
// worker is not found and the map stays blank. Pointing to the real file fixes dev and build.
setWorkerUrl(workerUrl);

// A free light map style, no API key needed.
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';
const START_VIEW = { longitude: -96, latitude: 38.5, zoom: 3.4 };

const EMPTY_FEATURES: FeatureCollection = { type: 'FeatureCollection', features: [] };

// A white outline under each route line, so routes stay readable where they overlap.
const ROUTE_CASING_LAYER: LayerProps = {
  id: 'routes-casing',
  type: 'line',
  layout: { 'line-cap': 'round', 'line-join': 'round' },
  paint: { 'line-color': '#ffffff', 'line-width': ['case', ['get', 'selected'], 10, 7] },
};

// The selected route is thick and solid, the others are thinner and faded.
const ROUTE_LINE_LAYER: LayerProps = {
  id: 'routes-line',
  type: 'line',
  layout: { 'line-cap': 'round', 'line-join': 'round' },
  paint: {
    'line-color': ['get', 'color'],
    'line-width': ['case', ['get', 'selected'], 6, 4],
    'line-opacity': ['case', ['get', 'selected'], 1, 0.55],
  },
};

const STOP_LAYER: LayerProps = {
  id: 'stops',
  type: 'circle',
  paint: {
    'circle-radius': 5,
    'circle-color': '#ffffff',
    'circle-stroke-color': '#212121',
    'circle-stroke-width': 2,
  },
};

const CHECKPOINT_LAYER: LayerProps = {
  id: 'checkpoints',
  type: 'circle',
  paint: {
    'circle-radius': 6,
    'circle-color': ['get', 'color'],
    'circle-stroke-color': '#ffffff',
    'circle-stroke-width': 2,
  },
};

// A black ring around the checkpoint that the mouse is over in the timeline.
const HIGHLIGHT_LAYER: LayerProps = {
  id: 'highlight',
  type: 'circle',
  paint: {
    'circle-radius': 11,
    'circle-color': 'rgba(0, 0, 0, 0)',
    'circle-stroke-color': '#000000',
    'circle-stroke-width': 3,
  },
};

function routesToGeoJson(routes: RouteOption[], selectedRouteId: string): FeatureCollection {
  // Draw the selected route last, so it sits on top of the others.
  const drawOrder = [...routes].sort(
    (a, b) => Number(a.id === selectedRouteId) - Number(b.id === selectedRouteId),
  );
  return {
    type: 'FeatureCollection',
    features: drawOrder.map((route) => ({
      type: 'Feature',
      properties: {
        id: route.id,
        color: ROUTE_COLORS[route.id] ?? '#444444',
        selected: route.id === selectedRouteId,
      },
      geometry: { type: 'LineString', coordinates: route.coordinates },
    })),
  };
}

function checkpointsToGeoJson(route: RouteOption | undefined): FeatureCollection {
  if (!route) {
    return EMPTY_FEATURES;
  }
  return {
    type: 'FeatureCollection',
    features: route.checkpoints.map((checkpoint, index) => ({
      type: 'Feature',
      properties: { index, color: RISK_COLORS[checkpoint.level] },
      geometry: { type: 'Point', coordinates: [checkpoint.lon, checkpoint.lat] },
    })),
  };
}

function stopsToGeoJson(route: RouteOption | undefined): FeatureCollection {
  if (!route) {
    return EMPTY_FEATURES;
  }
  return {
    type: 'FeatureCollection',
    features: route.stops.map((stop) => ({
      type: 'Feature',
      properties: { kind: stop.kind },
      geometry: { type: 'Point', coordinates: [stop.lon, stop.lat] },
    })),
  };
}

interface RouteMapProps {
  plan: PlanResponse | null;
  selectedRouteId: string;
  onSelectRoute: (routeId: string) => void;
  highlightedCheckpoint: number | null;
  // The weather for the hour on the slider, as map points. Null until it has loaded.
  heatData: FeatureCollection | null;
  // Where the truck is at the slider time. Null when it is not on the road at that time.
  truckLocation: LonLat | null;
}

export function RouteMap({
  plan,
  selectedRouteId,
  onSelectRoute,
  highlightedCheckpoint,
  heatData,
  truckLocation,
}: RouteMapProps) {
  const mapRef = useRef<MapRef>(null);
  // The checkpoint under the mouse (for the popup) and whether the mouse is over a route line.
  const [hoveredCheckpoint, setHoveredCheckpoint] = useState<number | null>(null);
  const [overRoute, setOverRoute] = useState(false);

  const selectedRoute = plan?.routes.find((route) => route.id === selectedRouteId);

  // The sources are always shown, empty when there is no plan. That keeps the layer order fixed.
  const routesGeoJson = useMemo(
    () => (plan ? routesToGeoJson(plan.routes, selectedRouteId) : EMPTY_FEATURES),
    [plan, selectedRouteId],
  );
  const checkpointsGeoJson = useMemo(() => checkpointsToGeoJson(selectedRoute), [selectedRoute]);
  const stopsGeoJson = useMemo(() => stopsToGeoJson(selectedRoute), [selectedRoute]);
  const highlightGeoJson = useMemo<FeatureCollection>(() => {
    const checkpoint =
      highlightedCheckpoint === null
        ? undefined
        : selectedRoute?.checkpoints[highlightedCheckpoint];
    if (!checkpoint) {
      return EMPTY_FEATURES;
    }
    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Point', coordinates: [checkpoint.lon, checkpoint.lat] },
        },
      ],
    };
  }, [highlightedCheckpoint, selectedRoute]);

  // Zoom the map to show every route whenever a new plan arrives.
  useEffect(() => {
    if (!plan) {
      return;
    }
    let west = Infinity;
    let south = Infinity;
    let east = -Infinity;
    let north = -Infinity;
    for (const route of plan.routes) {
      for (const [longitude, latitude] of route.coordinates) {
        west = Math.min(west, longitude);
        east = Math.max(east, longitude);
        south = Math.min(south, latitude);
        north = Math.max(north, latitude);
      }
    }
    mapRef.current?.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      // Extra room at the bottom, because the forecast panel covers that part of the map.
      { padding: { top: 48, left: 48, right: 48, bottom: 200 }, duration: 800 },
    );
  }, [plan]);

  function handleMouseMove(event: MapLayerMouseEvent) {
    // The first feature is the one on top.
    const feature = event.features?.[0];
    setHoveredCheckpoint(
      feature?.layer.id === 'checkpoints' ? Number(feature.properties.index) : null,
    );
    setOverRoute(feature?.layer.id === 'routes-line');
  }

  function handleMouseLeave() {
    setHoveredCheckpoint(null);
    setOverRoute(false);
  }

  function handleClick(event: MapLayerMouseEvent) {
    const feature = event.features?.[0];
    if (feature?.layer.id === 'routes-line') {
      onSelectRoute(String(feature.properties.id));
      setHoveredCheckpoint(null);
    }
  }

  const popupCheckpoint =
    hoveredCheckpoint === null ? undefined : selectedRoute?.checkpoints[hoveredCheckpoint];

  return (
    <Box sx={{ width: '100%', height: '100%' }}>
      <MapView
        ref={mapRef}
        initialViewState={START_VIEW}
        mapStyle={MAP_STYLE}
        interactiveLayerIds={['checkpoints', 'routes-line']}
        cursor={hoveredCheckpoint !== null || overRoute ? 'pointer' : ''}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
        style={{ width: '100%', height: '100%' }}
      >
        <NavigationControl position="top-right" showCompass={false} />

        <Source id="routes" type="geojson" data={routesGeoJson}>
          <Layer {...ROUTE_CASING_LAYER} />
          <Layer {...ROUTE_LINE_LAYER} />
        </Source>
        {/* beforeId puts the heatmap under the route lines, so the routes stay on top of it. */}
        <Source id="corridor-heat" type="geojson" data={heatData ?? EMPTY_FEATURES}>
          <Layer {...HEATMAP_LAYER} beforeId="routes-casing" />
        </Source>
        <Source id="stops" type="geojson" data={stopsGeoJson}>
          <Layer {...STOP_LAYER} />
        </Source>
        <Source id="checkpoints" type="geojson" data={checkpointsGeoJson}>
          <Layer {...CHECKPOINT_LAYER} />
        </Source>
        <Source id="highlight" type="geojson" data={highlightGeoJson}>
          <Layer {...HIGHLIGHT_LAYER} />
        </Source>

        {truckLocation && (
          <Marker longitude={truckLocation[0]} latitude={truckLocation[1]} anchor="center">
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                color: '#ffffff',
                border: '2px solid #ffffff',
                boxShadow: 3,
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <LocalShippingIcon fontSize="small" />
            </Box>
          </Marker>
        )}

        {plan && popupCheckpoint && (
          <Popup
            longitude={popupCheckpoint.lon}
            latitude={popupCheckpoint.lat}
            anchor="bottom"
            offset={12}
            closeButton={false}
            closeOnClick={false}
          >
            <Stack spacing={0.5} sx={{ minWidth: 200 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Chip
                  size="small"
                  label={RISK_LABELS[popupCheckpoint.level]}
                  sx={riskChipSx(popupCheckpoint.level)}
                />
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Mile {Math.round(popupCheckpoint.mile)}
                </Typography>
              </Stack>
              <Typography variant="caption">
                {formatTime(popupCheckpoint.eta, plan.timezone)}
              </Typography>
              <Typography variant="caption">{describeWeather(popupCheckpoint.weather)}</Typography>
              {popupCheckpoint.reasons.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  Because of: {popupCheckpoint.reasons.join(', ')}
                </Typography>
              )}
            </Stack>
          </Popup>
        )}
      </MapView>
    </Box>
  );
}
