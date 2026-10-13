import Alert from '@mui/material/Alert';
import Stack from '@mui/material/Stack';
import type { TripWarning } from '../api';

interface WarningsListProps {
  warnings: TripWarning[];
}

// The server writes the messages and picks the severity, so each one maps straight to an Alert.
export function WarningsList({ warnings }: WarningsListProps) {
  if (warnings.length === 0) {
    return null;
  }
  return (
    <Stack spacing={1}>
      {warnings.map((warning) => (
        <Alert key={warning.message} severity={warning.severity} variant="outlined">
          {warning.message}
        </Alert>
      ))}
    </Stack>
  );
}
