from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField


class FuelStation(models.Model):
    """
    Model representing a fuel station with location and pricing information.

    Attributes:
        station_id: Unique identifier for the station from OPIS
        name: Name of the truck stop
        address: Physical address of the station
        city: City where the station is located
        state: US state where the station is located
        rack_id: Rack identifier for pricing purposes
        retail_price: Current retail price of fuel
        location: Geographic point representing the station's location
        created_at: Timestamp of when the record was created
        updated_at: Timestamp of when the record was last updated
    """

    station_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(max_digits=6, decimal_places=3)
    location = models.PointField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:

        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["retail_price"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.city}, {self.state}"


class Route(models.Model):
    """
    Model representing a calculated route with fuel stops.

    Attributes:
        start_location: Starting point address
        end_location: Destination address
        start_coords: Geographic point of start location
        end_coords: Geographic point of end location
        total_distance: Total route distance in miles
        total_fuel_cost: Calculated total cost of fuel for the trip
        fuel_stops: Array of FuelStation IDs representing optimal fuel stops
        route_polyline: Encoded polyline of the route for map display
        created_at: Timestamp of when the route was created
    """

    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    start_coords = models.PointField()
    end_coords = models.PointField()
    total_distance = models.DecimalField(max_digits=8, decimal_places=2)
    total_fuel_cost = models.DecimalField(max_digits=8, decimal_places=2)
    fuel_stops = ArrayField(models.IntegerField())
    route_polyline = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Route from {self.start_location} to {self.end_location}"
