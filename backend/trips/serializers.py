from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import serializers
from timezonefinder import TimezoneFinder

from trips.geometry import haversine_mi
from trips.routing import MAX_LOAD_LB

MIN_TRIP_MI = 5
MAX_DAYS_AHEAD = 5
# Create it once. Loading the time zone data is slow.
TIMEZONE_FINDER = TimezoneFinder()


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class PlanRequestSerializer(serializers.Serializer):
    driver_name = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default=""
    )
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.CharField(
        help_text="Local time at the origin, YYYY-MM-DDTHH:MM"
    )
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=[10, 25, 50])

    def validate(self, attrs):
        """Checks that involve more than one field. Runs after each field is valid."""
        origin, destination = attrs["origin"], attrs["destination"]
        trip_miles = haversine_mi(
            (origin["lat"], origin["lon"]), (destination["lat"], destination["lon"])
        )
        if trip_miles < MIN_TRIP_MI:
            raise serializers.ValidationError(
                {"destination": "Destination is too close to the origin."}
            )
        try:
            local_departure = datetime.fromisoformat(attrs["departure"]).replace(
                tzinfo=None
            )
        except ValueError:
            raise serializers.ValidationError(
                {"departure": "Use the format YYYY-MM-DDTHH:MM."}
            )
        # The departure time is typed in the time zone of the origin. Convert it to UTC.
        timezone_name = (
            TIMEZONE_FINDER.timezone_at(lng=origin["lon"], lat=origin["lat"]) or "UTC"
        )
        departure_utc = local_departure.replace(
            tzinfo=ZoneInfo(timezone_name)
        ).astimezone(UTC)
        now_utc = timezone.now()
        # One hour of tolerance, so "the current hour" is not rejected.
        if departure_utc < now_utc - timedelta(hours=1):
            raise serializers.ValidationError(
                {"departure": "Departure is in the past."}
            )
        if departure_utc > now_utc + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(
                {
                    "departure": f"Departure must be within the next {MAX_DAYS_AHEAD} days."
                }
            )
        attrs["departure_utc"] = departure_utc
        attrs["timezone_name"] = timezone_name
        return attrs


class CorridorForecastRequestSerializer(serializers.Serializer):
    # Each point is [lat, lon]. Capped so one request cannot ask for thousands of forecasts.
    points = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(), min_length=2, max_length=2
        ),
        min_length=1,
        max_length=400,
    )
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    # When the 48 hour forecast starts, normally the departure from /api/plan. Defaults to now.
    start = serializers.DateTimeField(required=False)
