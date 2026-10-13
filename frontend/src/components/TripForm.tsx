import { useState, type FormEvent } from 'react';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import InputAdornment from '@mui/material/InputAdornment';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import type { Place, PlanRequest } from '../api';
import { PlaceAutocomplete } from './PlaceAutocomplete';

const MAX_LOAD_LB = 80000;
const INTERVAL_OPTIONS: PlanRequest['interval_mi'][] = [10, 25, 50];

// The next full hour in the browser's time, formatted for a datetime-local input.
function nextFullHourLocal(): string {
  const nextHour = new Date();
  nextHour.setMinutes(0, 0, 0);
  nextHour.setHours(nextHour.getHours() + 1);
  const pad = (part: number) => String(part).padStart(2, '0');
  const date = `${nextHour.getFullYear()}-${pad(nextHour.getMonth() + 1)}-${pad(nextHour.getDate())}`;
  return `${date}T${pad(nextHour.getHours())}:00`;
}

interface TripFormProps {
  loading: boolean;
  // Messages from the server, per field name (origin, destination, departure, load_lb).
  fieldErrors: Record<string, string>;
  onSubmit: (planRequest: PlanRequest) => void;
}

export function TripForm({ loading, fieldErrors, onSubmit }: TripFormProps) {
  const [driverName, setDriverName] = useState('');
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [departure, setDeparture] = useState(nextFullHourLocal);
  const [loadText, setLoadText] = useState('30000');
  const [intervalMiles, setIntervalMiles] = useState<PlanRequest['interval_mi']>(25);

  const loadLb = Number(loadText);
  const loadInvalid = loadText === '' || Number.isNaN(loadLb) || loadLb < 0 || loadLb > MAX_LOAD_LB;
  const canSubmit = Boolean(origin && destination && departure) && !loadInvalid && !loading;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!origin || !destination || !canSubmit) return;
    onSubmit({
      driver_name: driverName,
      origin,
      destination,
      departure,
      load_lb: loadLb,
      interval_mi: intervalMiles,
    });
  }

  return (
    <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        Plan a trip
      </Typography>
      <TextField
        label="Driver name (optional)"
        size="small"
        value={driverName}
        onChange={(event) => setDriverName(event.target.value)}
        slotProps={{ htmlInput: { maxLength: 40 } }}
      />
      <PlaceAutocomplete
        label="From"
        value={origin}
        onChange={setOrigin}
        error={fieldErrors.origin}
      />
      <PlaceAutocomplete
        label="To"
        value={destination}
        onChange={setDestination}
        error={fieldErrors.destination}
      />
      <TextField
        label="Departure (local time at origin)"
        type="datetime-local"
        size="small"
        value={departure}
        onChange={(event) => setDeparture(event.target.value)}
        error={Boolean(fieldErrors.departure)}
        helperText={fieldErrors.departure}
        slotProps={{ inputLabel: { shrink: true } }}
      />
      <TextField
        label="Cargo weight"
        type="number"
        size="small"
        value={loadText}
        onChange={(event) => setLoadText(event.target.value)}
        error={loadInvalid || Boolean(fieldErrors.load_lb)}
        helperText={fieldErrors.load_lb ?? 'Cargo only. The truck itself adds about 35,000 lb.'}
        slotProps={{
          input: { endAdornment: <InputAdornment position="end">lb</InputAdornment> },
          htmlInput: { min: 0, max: MAX_LOAD_LB, step: 500 },
        }}
      />
      <Stack spacing={0.5}>
        <Typography variant="caption" color="text.secondary">
          Check weather every
        </Typography>
        <ToggleButtonGroup
          exclusive
          fullWidth
          size="small"
          value={intervalMiles}
          onChange={(_event, picked: PlanRequest['interval_mi'] | null) => {
            // Clicking the selected button gives null. Ignore it so one option stays selected.
            if (picked) setIntervalMiles(picked);
          }}
        >
          {INTERVAL_OPTIONS.map((miles) => (
            <ToggleButton key={miles} value={miles}>
              {miles} mi
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>
      <Button
        type="submit"
        variant="contained"
        disabled={!canSubmit}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : null}
      >
        {loading ? 'Planning…' : 'Plan route'}
      </Button>
    </Stack>
  );
}
