import { useEffect, useState } from 'react';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { searchPlaces, type Place } from '../api';

const MIN_QUERY_LENGTH = 3;
// Wait this long after the last keystroke before asking the server.
const DEBOUNCE_MS = 300;

interface PlaceAutocompleteProps {
  label: string;
  value: Place | null;
  onChange: (place: Place | null) => void;
  error?: string;
}

export function PlaceAutocomplete({ label, value, onChange, error }: PlaceAutocompleteProps) {
  const [inputText, setInputText] = useState('');
  const [foundPlaces, setFoundPlaces] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);

  const query = inputText.trim();
  // No search for short text, or when the text is just the place that is already selected.
  const shouldSearch = query.length >= MIN_QUERY_LENGTH && query !== value?.label;

  useEffect(() => {
    if (!shouldSearch) {
      return;
    }
    // The controller lets us cancel the request if the user keeps typing.
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        setFoundPlaces(await searchPlaces(query, controller.signal));
      } catch {
        if (!controller.signal.aborted) {
          setFoundPlaces([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setSearching(false);
        }
      }
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, shouldSearch]);

  const options = shouldSearch ? foundPlaces : value ? [value] : [];

  return (
    <Autocomplete
      options={options}
      value={value}
      loading={shouldSearch && searching}
      // The server already filtered the places, so do not filter them again here.
      filterOptions={(placeOptions) => placeOptions}
      getOptionLabel={(place) => place.label}
      isOptionEqualToValue={(option, selected) => option.label === selected.label}
      onChange={(_event, place) => onChange(place)}
      onInputChange={(_event, text) => setInputText(text)}
      noOptionsText={
        query.length < MIN_QUERY_LENGTH ? 'Type at least 3 letters' : 'No places found'
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          size="small"
          error={Boolean(error)}
          helperText={error}
        />
      )}
    />
  );
}
