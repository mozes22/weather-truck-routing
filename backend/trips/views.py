from typing import Any, cast

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from trips import corridor, planner, routing
from trips.serializers import CorridorForecastRequestSerializer, PlanRequestSerializer
from trips.weather import WeatherUnavailable

# Do not call HERE for one or two letters.
MIN_GEOCODE_QUERY = 3


# @api_view turns a plain function into an API view that only accepts the listed methods.
@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def geocode(request):
    """Place suggestions for the autocomplete. The HERE key stays on the server."""
    query = request.query_params.get("q", "").strip()
    if len(query) < MIN_GEOCODE_QUERY:
        return Response([])
    try:
        return Response(routing.geocode(query))
    except routing.RoutingError as error:
        return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    # Invalid input stops here and DRF answers 400 with one message per field.
    serializer.is_valid(raise_exception=True)
    # DRF has no type stubs, so tell the checker what validated_data really is (like "as" in TypeScript).
    trip_input = cast(dict[str, Any], serializer.validated_data)
    try:
        result = planner.plan_trip(
            driver_name=trip_input["driver_name"],
            origin=trip_input["origin"],
            destination=trip_input["destination"],
            departure_utc=trip_input["departure_utc"],
            timezone_name=trip_input["timezone_name"],
            load_lb=trip_input["load_lb"],
            interval_mi=trip_input["interval_mi"],
        )
    except routing.NoRouteFound as error:
        return Response(
            {"detail": str(error)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except routing.RoutingError as error:
        return Response(
            {"detail": f"Routing service unavailable, please try again. ({error})"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(result)


@api_view(["POST"])
def corridor_forecast(request):
    """Weather and risk for the heatmap, called right after /api/plan."""
    serializer = CorridorForecastRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    request_data = cast(dict[str, Any], serializer.validated_data)
    try:
        return Response(
            corridor.forecast_corridor(
                request_data["points"],
                request_data["load_lb"],
                start_utc=request_data.get("start"),
            )
        )
    except WeatherUnavailable as error:
        return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)
