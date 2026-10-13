import { useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { ApiError, planTrip, type PlanRequest, type PlanResponse } from './api';
import { formatDuration, formatMiles } from './format';
import { TripForm } from './components/TripForm';

// Temporary screen for Task 10. Task 11 replaces the result with the map and route cards.
export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  // Counts the requests, so a slow old answer cannot replace a newer one.
  const latestRequestId = useRef(0);

  async function handlePlan(planRequest: PlanRequest) {
    latestRequestId.current += 1;
    const requestId = latestRequestId.current;
    setLoading(true);
    setErrorMessage(null);
    setFieldErrors({});
    try {
      const result = await planTrip(planRequest);
      if (requestId === latestRequestId.current) setPlan(result);
    } catch (error) {
      if (requestId !== latestRequestId.current) return;
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
        setFieldErrors(error.fieldErrors);
      } else {
        setErrorMessage('Could not reach the server. Please try again.');
      }
    } finally {
      if (requestId === latestRequestId.current) setLoading(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 560, mx: 'auto', p: 2 }}>
      <Stack spacing={2}>
        <TripForm loading={loading} fieldErrors={fieldErrors} onSubmit={handlePlan} />
        {errorMessage && <Alert severity="error">{errorMessage}</Alert>}
        {plan && (
          <Stack spacing={1}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              Recommended: route {plan.recommended_route_id}
            </Typography>
            <Typography variant="body2">{plan.reason}</Typography>
            {plan.routes.map((route) => (
              <Typography key={route.id} variant="body2">
                Route {route.id}: {formatMiles(route.distance_mi)},{' '}
                {formatDuration(route.duration_s)}, average risk{' '}
                {route.summary.avg_risk ?? 'unknown'}
              </Typography>
            ))}
            {plan.warnings.map((warning) => (
              <Alert key={warning.message} severity={warning.severity} variant="outlined">
                {warning.message}
              </Alert>
            ))}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
