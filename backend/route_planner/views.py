from django.core.exceptions import ValidationError

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Route
from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services import RoutePlannerService


class RoutePlannerViewSet(viewsets.ViewSet):
    """
    ViewSet for route planning with optimal fuel stops.

    Provides API endpoints for calculating routes between two locations
    with the most cost-effective fuel stops along the way.
    """

    queryset = Route.objects.all()
    serializer_class = RouteRequestSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        # request_body=RouteRequestSerializer,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["start_location", "end_location"],
            properties={
                "start_location": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Starting location",
                    example="350 5th Ave, New York, NY 10118",
                ),
                "end_location": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Ending location",
                    example="20 W 34th St, New York, NY 10001",
                ),
            },
        ),
        responses={
            200: RouteResponseSerializer,
            400: "Invalid input parameters",
            500: "Internal server error",
        },
        operation_description="""
        Calculate a route between two locations with optimal fuel stops.
        
        Takes start and end locations within the USA and returns:
        - Complete route information
        - List of optimal fuel stops
        - Total distance and fuel cost
        - Route visualization data
        """,
        operation_summary="Plan route with optimal fuel stops",
    )
    def create(self, request: Request) -> Response:
        """
        Create a new route plan with optimal fuel stops.

        Args:
            request: HTTP request containing start and end locations

        Returns:
            Response containing route details and fuel stops
        """
        # Validate input
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Calculate route
            route_planner = RoutePlannerService()
            print(serializer.validated_data, flush=True)
            route = route_planner.plan_route(
                serializer.validated_data["start_location"],
                serializer.validated_data["end_location"],
            )

            # Serialize response
            response_serializer = RouteResponseSerializer(route)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred while planning the route"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        responses={
            200: RouteResponseSerializer(many=True),
            500: "Internal server error",
        },
        operation_description="Retrieve list of all calculated routes",
        operation_summary="List all routes",
    )
    def list(self, request: Request) -> Response:
        """
        List all calculated routes.

        Returns:
            Response containing all routes in the database
        """
        try:
            routes = Route.objects.all().order_by("-created_at")
            serializer = RouteResponseSerializer(routes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred while retrieving routes"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        responses={
            200: RouteResponseSerializer,
            404: "Route not found",
            500: "Internal server error",
        },
        operation_description="Retrieve details of a specific route",
        operation_summary="Get route details",
        manual_parameters=[
            openapi.Parameter(
                "id",
                openapi.IN_PATH,
                description="Route ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
    )
    def retrieve(self, request: Request, pk: int = None) -> Response:
        """
        Retrieve a specific route by ID.

        Args:
            request: HTTP request
            pk: Primary key of the route to retrieve

        Returns:
            Response containing route details
        """
        try:
            route = Route.objects.get(pk=pk)
            serializer = RouteResponseSerializer(route)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Route.DoesNotExist:
            return Response(
                {"error": f"Route with id {pk} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred while retrieving the route"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        responses={
            204: "Route deleted successfully",
            404: "Route not found",
            500: "Internal server error",
        },
        operation_description="Delete a specific route",
        operation_summary="Delete route",
        manual_parameters=[
            openapi.Parameter(
                "id",
                openapi.IN_PATH,
                description="Route ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
    )
    def destroy(self, request: Request, pk: int = None) -> Response:
        """
        Delete a specific route.

        Args:
            request: HTTP request
            pk: Primary key of the route to delete

        Returns:
            Empty response with appropriate status code
        """
        try:
            route = Route.objects.get(pk=pk)
            route.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Route.DoesNotExist:
            return Response(
                {"error": f"Route with id {pk} not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred while deleting the route"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
