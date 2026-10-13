import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Slider from '@mui/material/Slider';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import type { CorridorForecast } from '../api';
import { formatTime } from '../format';
import { HEAT_COLORS, HEAT_LAYER_KEYS, HEAT_LAYERS, type HeatLayerKey } from '../heatmap';

const MS_PER_HOUR = 3_600_000;
const HOUR_MARKS = [0, 12, 24, 36, 48].map((hour) => ({ value: hour, label: `+${hour}h` }));

interface ForecastPanelProps {
  // Null until the server has sent the heatmap data.
  forecast: CorridorForecast | null;
  loading: boolean;
  errorMessage: string | null;
  // Hours after the start of the forecast, from 0 to 48.
  hour: number;
  onHourChange: (hour: number) => void;
  layerKey: HeatLayerKey;
  onLayerChange: (layerKey: HeatLayerKey) => void;
  timezone: string;
}

export function ForecastPanel({
  forecast,
  loading,
  errorMessage,
  hour,
  onHourChange,
  layerKey,
  onLayerChange,
  timezone,
}: ForecastPanelProps) {
  const layer = HEAT_LAYERS[layerKey];
  const hourLabel = forecast
    ? `${formatTime(new Date(Date.parse(forecast.start) + hour * MS_PER_HOUR).toISOString(), timezone)} · +${hour} h`
    : 'Weather forecast';

  return (
    <Paper
      elevation={4}
      sx={{
        position: 'absolute',
        left: 16,
        bottom: 32,
        zIndex: 3,
        width: 'calc(100% - 32px)',
        maxWidth: 520,
        p: 1.5,
      }}
    >
      <Stack spacing={1}>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
          <TextField
            select
            size="small"
            label="Map layer"
            value={layerKey}
            onChange={(event) => {
              const pickedKey = HEAT_LAYER_KEYS.find((key) => key === event.target.value);
              if (pickedKey) {
                onLayerChange(pickedKey);
              }
            }}
            sx={{ minWidth: 120 }}
          >
            {HEAT_LAYER_KEYS.map((key) => (
              <MenuItem key={key} value={key}>
                {HEAT_LAYERS[key].label}
              </MenuItem>
            ))}
          </TextField>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {hourLabel}
          </Typography>
        </Stack>

        <Box>
          <Box
            sx={{
              height: 8,
              borderRadius: 4,
              background: `linear-gradient(to right, ${HEAT_COLORS.join(', ')})`,
            }}
          />
          <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
            <Typography variant="caption" color="text.secondary">
              {layer.lowLabel}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {layer.highLabel}
            </Typography>
          </Stack>
        </Box>

        <Slider
          aria-label="Forecast hour"
          min={0}
          max={48}
          step={1}
          marks={HOUR_MARKS}
          value={hour}
          disabled={!forecast}
          onChange={(_event, newValue) => {
            if (typeof newValue === 'number') {
              onHourChange(newValue);
            }
          }}
          sx={{ mx: 1, width: 'calc(100% - 16px)' }}
        />

        {loading && (
          <Stack spacing={0.5}>
            <LinearProgress />
            <Typography variant="caption" color="text.secondary">
              Loading the weather map. The routes are already ready.
            </Typography>
          </Stack>
        )}
        {errorMessage && (
          <Typography variant="caption" color="error">
            {errorMessage}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}
