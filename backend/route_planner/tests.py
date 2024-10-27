import json

from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from .models import FuelStation, Route
from .services import (
    FuelOptimizationService,
    MapQuestService,
    RoutePlannerService,
)


# Fixtures
@pytest.fixture
def api_client() -> APIClient:
    """Create a test API client."""
    return APIClient()


@pytest.fixture
def sample_stations() -> list[FuelStation]:
    """Create sample fuel stations for testing."""
    stations = [
        FuelStation.objects.create(
            station_id=1,
            name="Station 1",
            address="123 Main St",
            city="City1",
            state="CA",
            rack_id=1,
            retail_price=Decimal("3.50"),
            location=Point(-118.2437, 34.0522),  # Los Angeles
        ),
        FuelStation.objects.create(
            station_id=2,
            name="Station 2",
            address="456 Oak St",
            city="City2",
            state="AZ",
            rack_id=2,
            retail_price=Decimal("3.25"),
            location=Point(-112.0740, 33.4484),  # Phoenix
        ),
        FuelStation.objects.create(
            station_id=3,
            name="Station 3",
            address="789 Pine St",
            city="City3",
            state="NM",
            rack_id=3,
            retail_price=Decimal("3.75"),
            location=Point(-106.6504, 35.0844),  # Albuquerque
        ),
    ]
    return stations


@pytest.fixture
def sample_route(sample_stations: list[FuelStation]) -> Route:
    """Create a sample route for testing."""
    return Route.objects.create(
        start_location="Los Angeles, CA",
        end_location="New York, NY",
        start_coords=Point(-118.2437, 34.0522),
        end_coords=Point(-74.0060, 40.7128),
        total_distance=Decimal("2789.5"),
        total_fuel_cost=Decimal("875.25"),
        fuel_stops=[station.station_id for station in sample_stations],
        route_polyline="sample_polyline_data",
    )


@pytest.fixture
def mock_mapquest_response() -> dict[str, Any]:
    """Create mock MapQuest API response."""
    return {
        "route": {
            "distance": 2789.5,
            "shape": {
                "shapePoints": [
                    [34.0522, -118.2437],
                    [33.4484, -112.0740],
                    [35.0844, -106.6504],
                    [40.7128, -74.0060],
                ]
            },
        }
    }


# Model Tests
@pytest.mark.django_db
class TestFuelStation:
    """Test cases for the FuelStation model."""

    def test_fuel_station_creation(self) -> None:
        """Test creating a fuel station."""
        station = FuelStation.objects.create(
            station_id=1,
            name="Test Station",
            address="123 Test St",
            city="Test City",
            state="CA",
            rack_id=1,
            retail_price=Decimal("3.50"),
            location=Point(-118.2437, 34.0522),
        )
        assert station.name == "Test Station"
        assert station.retail_price == Decimal("3.50")
        assert station.location.x == -118.2437
        assert station.location.y == 34.0522

    def test_fuel_station_str(self, sample_stations: list[FuelStation]) -> None:
        """Test string representation of fuel station."""
        station = sample_stations[0]
        expected_str = f"{station.name} - {station.city}, {station.state}"
        assert str(station) == expected_str


# Service Tests
@pytest.mark.django_db
class TestMapQuestService:
    """Test cases for the MapQuest service."""

    @patch("requests.get")
    def test_get_route(
        self, mock_get: Mock, mock_mapquest_response: dict[str, Any]
    ) -> None:
        """Test route calculation using MapQuest API."""
        mock_get.return_value.json.return_value = mock_mapquest_response
        mock_get.return_value.raise_for_status.return_value = None

        service = MapQuestService()
        result = service.get_route("Los Angeles, CA", "New York, NY")

        assert result == mock_mapquest_response
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_geocode(self, mock_get: Mock) -> None:
        """Test address geocoding."""
        mock_response = {
            "results": [{"locations": [{"latLng": {"lat": 34.0522, "lng": -118.2437}}]}]
        }
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None

        service = MapQuestService()
        lat, lng = service.geocode("Los Angeles, CA")

        assert lat == 34.0522
        assert lng == -118.2437
        mock_get.assert_called_once()


@pytest.mark.django_db
class TestFuelOptimizationService:
    """Test cases for the fuel optimization service."""

    def test_find_optimal_stops(self, sample_stations: list[FuelStation]) -> None:
        """Test finding optimal fuel stops."""
        service = FuelOptimizationService()
        route_points = [
            (34.0522, -118.2437),
            (33.4484, -112.0740),
            (35.0844, -106.6504),
        ]

        stops, cost = service.find_optimal_stops(route_points, 1000.0)

        assert len(stops) > 0
        assert isinstance(cost, Decimal)
        assert cost > 0

    def test_get_stations_near_route(self, sample_stations: list[FuelStation]) -> None:
        """Test finding stations near route."""
        service = FuelOptimizationService()
        route_points = [(34.0522, -118.2437), (33.4484, -112.0740)]

        stations = service._get_stations_near_route(route_points)
        assert len(stations) > 0


# View Tests
@pytest.mark.django_db
class TestRoutePlannerViewSet:
    """Test cases for the RoutePlannerViewSet."""

    def test_create_route(
        self,
        api_client: APIClient,
        sample_stations: list[FuelStation],
        mock_mapquest_response: dict[str, Any],
    ) -> None:
        """Test route creation endpoint."""
        with patch(
            "route_planner.services.MapQuestService.get_route"
        ) as mock_get_route:
            mock_get_route.return_value = mock_mapquest_response

            data = {"start_location": "Los Angeles, CA", "end_location": "New York, NY"}

            response = api_client.post(
                "/api/route/", data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            assert "total_distance" in response.data
            assert "fuel_stops" in response.data
            assert "total_fuel_cost" in response.data

    def test_invalid_request(self, api_client: APIClient) -> None:
        """Test route creation with invalid data."""
        data = {
            "start_location": "",  # Invalid empty location
            "end_location": "New York, NY",
        }

        response = api_client.post(
            "/api/route/", data=json.dumps(data), content_type="application/json"
        )

        assert response.status_code == 400


# Management Command Tests
@pytest.mark.django_db
class TestLoadFuelDataCommand:
    """Test cases for the loadfueldata management command."""

    def test_load_fuel_data(self, tmp_path: str) -> None:
        """Test loading fuel data from CSV."""
        # Create test CSV file
        csv_content = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
1,Test Station,123 Test St,Test City,CA,1,3.50"""
        csv_file = tmp_path / "test_fuel_data.csv"
        csv_file.write_text(csv_content)

        with patch("route_planner.services.MapQuestService.geocode") as mock_geocode:
            mock_geocode.return_value = (34.0522, -118.2437)

            call_command("loadfueldata", f"--csv-file={csv_file}")

            assert FuelStation.objects.count() == 1
            station = FuelStation.objects.first()
            assert station.station_id == 1
            assert station.name == "Test Station"
            assert station.retail_price == Decimal("3.50")

    def test_skip_existing_data(
        self, sample_stations: list[FuelStation], tmp_path: str
    ) -> None:
        """Test skipping data load when stations exist."""
        csv_file = tmp_path / "test_fuel_data.csv"
        csv_file.write_text(
            "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price"
        )

        initial_count = FuelStation.objects.count()
        call_command("loadfueldata", f"--csv-file={csv_file}")
        assert FuelStation.objects.count() == initial_count

    def test_force_reload_data(
        self, sample_stations: list[FuelStation], tmp_path: str
    ) -> None:
        """Test force reloading data."""
        csv_content = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
1,New Station,123 New St,New City,CA,1,3.75"""
        csv_file = tmp_path / "test_fuel_data.csv"
        csv_file.write_text(csv_content)

        with patch("route_planner.services.MapQuestService.geocode") as mock_geocode:
            mock_geocode.return_value = (34.0522, -118.2437)

            call_command("loadfueldata", f"--csv-file={csv_file}", "--force")

            station = FuelStation.objects.get(station_id=1)
            assert station.name == "New Station"
            assert station.retail_price == Decimal("3.75")


# Integration Tests
@pytest.mark.django_db
class TestRouteIntegration:
    """Integration tests for the complete route planning flow."""

    def test_complete_route_planning(
        self,
        api_client: APIClient,
        sample_stations: list[FuelStation],
        mock_mapquest_response: dict[str, Any],
    ) -> None:
        """Test the complete route planning process."""
        with patch(
            "route_planner.services.MapQuestService.get_route"
        ) as mock_get_route, patch(
            "route_planner.services.MapQuestService.geocode"
        ) as mock_geocode:

            mock_get_route.return_value = mock_mapquest_response
            mock_geocode.return_value = (34.0522, -118.2437)

            data = {"start_location": "Los Angeles, CA", "end_location": "New York, NY"}

            # Clear cache
            cache.clear()

            # Make request
            response = api_client.post(
                "/api/route/", data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200

            # Verify route was created
            route_id = response.data["id"]
            route = Route.objects.get(id=route_id)

            assert route.start_location == "Los Angeles, CA"
            assert route.end_location == "New York, NY"
            assert len(route.fuel_stops) > 0

            # Verify cache was populated
            cache_key = f"route_{data['start_location']}_{data['end_location']}"
            assert cache.get(cache_key) is not None
