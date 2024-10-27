from decimal import Decimal
from typing import Any, Tuple
import logging
from functools import wraps

import numpy as np
import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.cache import cache

from .models import FuelStation, Route

logger = logging.getLogger(__name__)


def cache_safe(func):
    """
    Decorator to handle cache operations safely.
    If cache is unavailable, the wrapped function will still work without caching.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Try to get from cache first
            cache_key = f"{func.__name__}_{str(args[1:])}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        except Exception as e:
            logger.warning(
                f"Cache retrieval failed: {str(e)}. Proceeding without cache."
            )

        # Execute the function
        result = func(*args, **kwargs)

        # Try to cache the result
        try:
            cache.set(cache_key, result, settings.ROUTE_CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Cache storage failed: {str(e)}. Proceeding without cache.")

        return result

    return wrapper


class MapQuestService:
    """
    Service for interacting with the MapQuest API.

    Handles route calculations and geocoding using MapQuest's API services.
    Includes fault-tolerant caching and comprehensive error handling.
    """

    def __init__(self) -> None:
        self.api_key = settings.MAP_QUEST_API_KEY
        self.base_url = settings.MAP_QUEST_URL
        self.retries = 3  # Number of retries for API calls

    @cache_safe
    def get_route(self, start: str, end: str) -> dict[str, Any]:
        """
        Calculate route between two locations using MapQuest API.

        Args:
            start: Starting location address
            end: Destination address

        Returns:
            Dictionary containing route information including distance and polyline

        Raises:
            ValueError: If the API returns invalid or missing data
            requests.RequestException: If the API request fails
        """
        for attempt in range(self.retries):
            try:
                response = requests.get(
                    f"{self.base_url}/directions/v2/route",
                    params={
                        "key": self.api_key,
                        "from": start,
                        "to": end,
                        "routeType": "fastest",
                        "fullShape": True,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()

                # Validate response structure
                if "route" not in result or "shape" not in result["route"]:
                    raise ValueError("Invalid response structure from MapQuest API")

                return result

            except requests.RequestException as e:
                if attempt == self.retries - 1:  # Last attempt
                    logger.error(
                        f"Failed to get route after {self.retries} attempts: {str(e)}"
                    )
                    raise
                logger.warning(
                    f"Route calculation attempt {attempt + 1} failed: {str(e)}"
                )

            except Exception as e:
                logger.error(f"Unexpected error in get_route: {str(e)}")
                raise

    @cache_safe
    def geocode(self, address: str) -> Tuple[float, float]:
        """
        Convert address to coordinates using MapQuest API.

        Args:
            address: Location address to geocode

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            ValueError: If geocoding fails or returns invalid data
            requests.RequestException: If the API request fails
        """
        for attempt in range(self.retries):
            try:
                response = requests.get(
                    f"{self.base_url}/geocoding/v1/address",
                    params={"key": self.api_key, "location": address},
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()

                # Validate response structure
                if not result.get("results"):
                    raise ValueError(f"No results found for address: {address}")

                if not result["results"][0].get("locations"):
                    raise ValueError(f"No locations found for address: {address}")

                location = result["results"][0]["locations"][0].get("latLng")
                if not location or "lat" not in location or "lng" not in location:
                    raise ValueError(f"Invalid location data for address: {address}")

                return (location["lat"], location["lng"])

            except requests.RequestException as e:
                if attempt == self.retries - 1:  # Last attempt
                    logger.error(
                        f"Failed to geocode after {self.retries} attempts: {str(e)}"
                    )
                    raise
                logger.warning(f"Geocoding attempt {attempt + 1} failed: {str(e)}")

            except Exception as e:
                logger.error(f"Unexpected error in geocode: {str(e)}")
                raise

    def _handle_api_error(self, response: requests.Response) -> None:
        """
        Handle API errors with appropriate logging and error messages.

        Args:
            response: Response object from requests

        Raises:
            requests.RequestException: With appropriate error message
        """
        try:
            error_data = response.json()
            error_message = error_data.get("messages", ["Unknown API error"])[0]
        except Exception:
            error_message = response.text or "Unknown API error"

        logger.error(f"MapQuest API error: {error_message}")
        raise requests.RequestException(f"API error: {error_message}")
