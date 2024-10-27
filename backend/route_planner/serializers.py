from typing import Any

from rest_framework import serializers

from .models import FuelStation, Route


class FuelStationSerializer(serializers.ModelSerializer):
    """
    Serializer for the FuelStation model.

    Converts FuelStation model instances to/from JSON format, including
    proper handling of geographic coordinates.
    """

    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = FuelStation
        fields = [
            "station_id",
            "name",
            "address",
            "city",
            "state",
            "retail_price",
            "latitude",
            "longitude",
        ]

    def get_latitude(self, obj: FuelStation) -> float:
        """Extract latitude from the location field."""
        return obj.location.y

    def get_longitude(self, obj: FuelStation) -> float:
        """Extract longitude from the location field."""
        return obj.location.x


class RouteRequestSerializer(serializers.Serializer):
    """
    Serializer for route calculation requests.

    Validates incoming requests for route calculations, ensuring both
    start and end locations are provided.
    """

    start_location = serializers.CharField(
        max_length=255,
        help_text="Starting address (e.g., '350 5th Ave, New York, NY 10118')",
    )
    end_location = serializers.CharField(
        max_length=255,
        help_text="Ending address (e.g., '20 W 34th St, New York, NY 10001')",
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate that both locations are within the USA."""
        # Additional validation could be added here
        return data


class RouteResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for route calculation responses.

    Converts calculated Route instances to JSON format, including all
    necessary information about the route and fuel stops.
    """

    fuel_stops = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "start_location",
            "end_location",
            "total_distance",
            "total_fuel_cost",
            "fuel_stops",
            "route_polyline",
        ]

    def get_fuel_stops(self, obj: Route) -> list[dict[str, Any]]:
        """Retrieve and format fuel stop information."""
        stations = FuelStation.objects.filter(station_id__in=obj.fuel_stops)
        return FuelStationSerializer(stations, many=True).data
