import StarIcon from '@mui/icons-material/Star';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { RouteOption, RouteSummary } from '../api';
import { formatDuration, formatMiles, formatTime } from '../format';
import { RISK_LABELS, ROUTE_COLORS, riskChipSx } from '../riskStyle';

interface RouteCardsProps {
  routes: RouteOption[];
  recommendedId: string;
  // One sentence from the server about why the recommended route won.
  reason: string;
  selectedId: string;
  timezone: string;
  onSelect: (routeId: string) => void;
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

// Chips for the miles at each dangerous level. A route without any shows one reassuring chip.
function RiskMilesChips({ summary }: { summary: RouteSummary }) {
  const dangerousLevels = [
    { level: 'no_travel', miles: summary.no_travel_mi },
    { level: 'severe', miles: summary.severe_mi },
    { level: 'high', miles: summary.high_mi },
  ] as const;
  const shownLevels = dangerousLevels.filter(({ miles }) => miles > 0);

  return (
    <>
      {shownLevels.map(({ level, miles }) => (
        <Chip
          key={level}
          size="small"
          label={`${formatMiles(miles)} ${RISK_LABELS[level]}`}
          sx={riskChipSx(level)}
        />
      ))}
      {shownLevels.length === 0 && (
        <Chip size="small" color="success" variant="outlined" label="No High or Severe miles" />
      )}
      {summary.unknown_mi > 0 && (
        <Chip
          size="small"
          variant="outlined"
          label={`${formatMiles(summary.unknown_mi)} no forecast`}
        />
      )}
    </>
  );
}

export function RouteCards({
  routes,
  recommendedId,
  reason,
  selectedId,
  timezone,
  onSelect,
}: RouteCardsProps) {
  // Best route first.
  const rankedRoutes = [...routes].sort((a, b) => a.summary.rank - b.summary.rank);

  return (
    <Stack spacing={1.5}>
      {rankedRoutes.map((route) => {
        const isSelected = route.id === selectedId;
        const breakCount = route.stops.filter((stop) => stop.kind === 'break').length;
        const restCount = route.stops.filter((stop) => stop.kind === 'rest').length;
        const averageRisk =
          route.summary.avg_risk === null ? 'n/a' : route.summary.avg_risk.toFixed(2);

        return (
          <Card
            key={route.id}
            variant="outlined"
            // Both states use a 2 px border, so selecting a card does not shift the layout.
            sx={{ borderWidth: 2, borderColor: isSelected ? 'primary.main' : 'divider' }}
          >
            <CardActionArea onClick={() => onSelect(route.id)} aria-pressed={isSelected}>
              <CardContent>
                <Stack spacing={1}>
                  <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                    <Box
                      sx={{
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        bgcolor: ROUTE_COLORS[route.id],
                        color: '#ffffff',
                        display: 'grid',
                        placeItems: 'center',
                        fontWeight: 700,
                        fontSize: 14,
                      }}
                    >
                      {route.id}
                    </Box>
                    <Typography sx={{ fontWeight: 700, flexGrow: 1 }}>
                      {formatDuration(route.duration_s)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatMiles(route.distance_mi)}
                    </Typography>
                  </Stack>

                  {route.id === recommendedId && (
                    <Stack spacing={0.5}>
                      <Chip
                        size="small"
                        color="primary"
                        icon={<StarIcon />}
                        label="Recommended"
                        sx={{ alignSelf: 'flex-start' }}
                      />
                      <Typography variant="body2">{reason}</Typography>
                    </Stack>
                  )}

                  <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap', gap: 0.75 }}>
                    <RiskMilesChips summary={route.summary} />
                    <Chip size="small" variant="outlined" label={`Avg risk ${averageRisk}`} />
                  </Stack>

                  <Typography variant="caption" color="text.secondary">
                    Arrives {formatTime(route.arrival, timezone)} · {plural(breakCount, 'break')},{' '}
                    {plural(restCount, 'overnight rest')} · {formatDuration(route.driving_s)}{' '}
                    driving
                  </Typography>
                </Stack>
              </CardContent>
            </CardActionArea>
          </Card>
        );
      })}
    </Stack>
  );
}
