import { useMemo, useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import {
  ApiError,
  fetchCorridorForecast,
  planTrip,
  type CorridorForecast,
  type PlanRequest,
  type PlanResponse,
} from './api';
import { ForecastPanel } from './components/ForecastPanel';
import { RouteCards } from './components/RouteCards';
import { RouteMap } from './components/RouteMap';
import { Timeline } from './components/Timeline';
import { TripForm } from './components/TripForm';
import { WarningsList } from './components/WarningsList';
import { cumulativeMiles, truckPosition } from './geo';
import { heatDataFor, type HeatLayerKey } from './heatmap';

const MS_PER_HOUR = 3_600_000;
const LAST_FORECAST_HOUR = 48;

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState('');
  // The checkpoint the mouse is over in the timeline, shown as a ring on the map.
  const [highlightedCheckpoint, setHighlightedCheckpoint] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  // The heatmap data arrives after the plan, because it takes longer to fetch.
  const [forecast, setForecast] = useState<CorridorForecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);
  const [heatLayerKey, setHeatLayerKey] = useState<HeatLayerKey>('risk');
  // Hours after the start of the forecast. This is the slider value.
  const [forecastHour, setForecastHour] = useState(0);
  // Counts the requests, so a slow old answer cannot replace a newer one.
  const latestRequestId = useRef(0);

  const selectedRoute = plan?.routes.find((route) => route.id === selectedRouteId);

  // Changing the slider only picks another hour of data that is already in memory.
  const heatData = useMemo(
    () => (forecast ? heatDataFor(forecast, heatLayerKey, forecastHour) : null),
    [forecast, heatLayerKey, forecastHour],
  );
  const selectedRouteMiles = useMemo(
    () => (selectedRoute ? cumulativeMiles(selectedRoute.coordinates) : []),
    [selectedRoute],
  );
  const truck = useMemo(() => {
    if (!forecast || !selectedRoute) {
      return null;
    }
    const sliderTimeMs = Date.parse(forecast.start) + forecastHour * MS_PER_HOUR;
    return truckPosition(selectedRoute, selectedRouteMiles, sliderTimeMs);
  }, [forecast, selectedRoute, selectedRouteMiles, forecastHour]);

  async function loadForecast(result: PlanResponse, loadLb: number, requestId: number) {
    setForecastLoading(true);
    try {
      const corridorForecast = await fetchCorridorForecast(result.corridor_grid, loadLb);
      if (requestId !== latestRequestId.current) {
        return;
      }
      setForecast(corridorForecast);
      // Start the slider at the hour the trip begins.
      const hoursUntilDeparture = Math.round(
        (Date.parse(result.departure) - Date.parse(corridorForecast.start)) / MS_PER_HOUR,
      );
      setForecastHour(Math.min(Math.max(hoursUntilDeparture, 0), LAST_FORECAST_HOUR));
    } catch (error) {
      if (requestId !== latestRequestId.current) {
        return;
      }
      setForecastError(
        error instanceof ApiError ? error.message : 'Could not load the weather map.',
      );
    } finally {
      if (requestId === latestRequestId.current) {
        setForecastLoading(false);
      }
    }
  }

  async function handlePlan(planRequest: PlanRequest) {
    latestRequestId.current += 1;
    const requestId = latestRequestId.current;
    setLoading(true);
    setErrorMessage(null);
    setFieldErrors({});
    setForecastLoading(false);
    try {
      const result = await planTrip(planRequest);
      if (requestId === latestRequestId.current) {
        setPlan(result);
        // Start with the recommended route selected.
        setSelectedRouteId(result.recommended_route_id);
        setHighlightedCheckpoint(null);
        setForecast(null);
        setForecastError(null);
        // The routes are shown now. The heatmap data loads in the background.
        loadForecast(result, planRequest.load_lb, requestId);
      }
    } catch (error) {
      if (requestId !== latestRequestId.current) {
        return;
      }
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
        setFieldErrors(error.fieldErrors);
      } else {
        setErrorMessage('Could not reach the server. Please try again.');
      }
    } finally {
      if (requestId === latestRequestId.current) {
        setLoading(false);
      }
    }
  }

  function handleSelectRoute(routeId: string) {
    setSelectedRouteId(routeId);
    setHighlightedCheckpoint(null);
  }

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '400px 1fr' },
        height: { md: '100vh' },
      }}
    >
      {/* On a phone the map comes first, then the form and results. */}
      <Box
        sx={{
          order: { xs: 2, md: 1 },
          p: 2,
          overflowY: { md: 'auto' },
          height: { md: '100vh' },
        }}
      >
        <Stack spacing={2}>
          <TripForm loading={loading} fieldErrors={fieldErrors} onSubmit={handlePlan} />
          {errorMessage && <Alert severity="error">{errorMessage}</Alert>}

          {loading && (
            <Stack spacing={1.5}>
              <Skeleton variant="rounded" height={64} />
              <Skeleton variant="rounded" height={120} />
              <Skeleton variant="rounded" height={120} />
              <Skeleton variant="rounded" height={120} />
            </Stack>
          )}

          {!loading && plan && selectedRoute && (
            <>
              <WarningsList warnings={plan.warnings} />
              <RouteCards
                routes={plan.routes}
                recommendedId={plan.recommended_route_id}
                reason={plan.reason}
                selectedId={selectedRoute.id}
                timezone={plan.timezone}
                onSelect={handleSelectRoute}
              />
              <Timeline
                route={selectedRoute}
                timezone={plan.timezone}
                highlightedIndex={highlightedCheckpoint}
                onHighlight={setHighlightedCheckpoint}
              />
            </>
          )}
        </Stack>
      </Box>

      {/* position: relative lets the forecast panel sit on top of the map. */}
      <Box
        sx={{ order: { xs: 1, md: 2 }, height: { xs: '55vh', md: '100vh' }, position: 'relative' }}
      >
        <RouteMap
          plan={plan}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
          highlightedCheckpoint={highlightedCheckpoint}
          heatData={heatData}
          truck={truck}
        />
        {plan && (
          <ForecastPanel
            forecast={forecast}
            loading={forecastLoading}
            errorMessage={forecastError}
            hour={forecastHour}
            onHourChange={setForecastHour}
            layerKey={heatLayerKey}
            onLayerChange={setHeatLayerKey}
            timezone={plan.timezone}
          />
        )}
      </Box>
    </Box>
  );
}
