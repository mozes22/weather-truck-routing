import { useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import { ApiError, planTrip, type PlanRequest, type PlanResponse } from './api';
import { RouteCards } from './components/RouteCards';
import { RouteMap } from './components/RouteMap';
import { Timeline } from './components/Timeline';
import { TripForm } from './components/TripForm';
import { WarningsList } from './components/WarningsList';

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState('');
  // The checkpoint the mouse is over in the timeline, shown as a ring on the map.
  const [highlightedCheckpoint, setHighlightedCheckpoint] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  // Counts the requests, so a slow old answer cannot replace a newer one.
  const latestRequestId = useRef(0);

  const selectedRoute = plan?.routes.find((route) => route.id === selectedRouteId);

  async function handlePlan(planRequest: PlanRequest) {
    latestRequestId.current += 1;
    const requestId = latestRequestId.current;
    setLoading(true);
    setErrorMessage(null);
    setFieldErrors({});
    try {
      const result = await planTrip(planRequest);
      if (requestId === latestRequestId.current) {
        setPlan(result);
        // Start with the recommended route selected.
        setSelectedRouteId(result.recommended_route_id);
        setHighlightedCheckpoint(null);
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

      <Box sx={{ order: { xs: 1, md: 2 }, height: { xs: '55vh', md: '100vh' } }}>
        <RouteMap
          plan={plan}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
          highlightedCheckpoint={highlightedCheckpoint}
        />
      </Box>
    </Box>
  );
}
