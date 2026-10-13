import HotelIcon from '@mui/icons-material/Hotel';
import LocalCafeIcon from '@mui/icons-material/LocalCafe';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useMemo } from 'react';
import type { Checkpoint, RouteOption, Stop } from '../api';
import { describeWeather, formatTime } from '../format';
import { RISK_LABELS, riskChipSx } from '../riskStyle';

interface TimelineProps {
  route: RouteOption;
  timezone: string;
  // Index of the checkpoint highlighted on the map, if any.
  highlightedIndex: number | null;
  onHighlight: (checkpointIndex: number | null) => void;
}

// Checkpoints and rest stops share one list, ordered by time.
type TimelineRow =
  | { kind: 'checkpoint'; timeMs: number; checkpointIndex: number; checkpoint: Checkpoint }
  | { kind: 'stop'; timeMs: number; stop: Stop };

function describeStop(stop: Stop): string {
  return stop.kind === 'break'
    ? `${stop.duration_min} min break`
    : `${stop.duration_min / 60} h rest (FMCSA)`;
}

export function Timeline({ route, timezone, highlightedIndex, onHighlight }: TimelineProps) {
  const rows = useMemo(() => {
    const checkpointRows: TimelineRow[] = route.checkpoints.map((checkpoint, checkpointIndex) => ({
      kind: 'checkpoint',
      timeMs: Date.parse(checkpoint.eta),
      checkpointIndex,
      checkpoint,
    }));
    const stopRows: TimelineRow[] = route.stops.map((stop) => ({
      kind: 'stop',
      timeMs: Date.parse(stop.start),
      stop,
    }));
    return [...checkpointRows, ...stopRows].sort((a, b) => a.timeMs - b.timeMs);
  }, [route]);

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        Route {route.id} timeline
      </Typography>
      <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
        {rows.map((row) => {
          if (row.kind === 'stop') {
            return (
              <Stack
                key={`stop-${row.stop.start}`}
                component="li"
                direction="row"
                spacing={1}
                sx={{ alignItems: 'center', py: 0.75, color: 'text.secondary' }}
              >
                {row.stop.kind === 'break' ? (
                  <LocalCafeIcon fontSize="small" />
                ) : (
                  <HotelIcon fontSize="small" />
                )}
                <Typography variant="body2">
                  {formatTime(row.stop.start, timezone)} · {describeStop(row.stop)}
                </Typography>
              </Stack>
            );
          }

          const { checkpoint, checkpointIndex } = row;
          return (
            <Stack
              key={`checkpoint-${checkpointIndex}`}
              component="li"
              direction="row"
              spacing={1}
              onMouseEnter={() => onHighlight(checkpointIndex)}
              onMouseLeave={() => onHighlight(null)}
              sx={{
                alignItems: 'center',
                py: 0.75,
                px: 0.5,
                borderRadius: 1,
                bgcolor: highlightedIndex === checkpointIndex ? 'action.hover' : 'transparent',
              }}
            >
              <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {formatTime(checkpoint.eta, timezone)} · mile {Math.round(checkpoint.mile)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {describeWeather(checkpoint.weather)}
                </Typography>
              </Box>
              <Chip
                size="small"
                label={RISK_LABELS[checkpoint.level]}
                // The reasons, such as "wind, load", show when hovering the chip.
                title={checkpoint.reasons.join(', ')}
                sx={riskChipSx(checkpoint.level)}
              />
            </Stack>
          );
        })}
      </Box>
    </Box>
  );
}
