import csv
import logging
import os
import time
from decimal import Decimal

from typing import Any, Set, Tuple, Optional
from functools import wraps

import redis
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import FuelStation
from ...services import MapQuestService

logger = logging.getLogger(__name__)


def retry_on_failure(retries=3, delay=1):
    """Decorator to retry operations with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:  # Last attempt
                        raise
                    wait_time = delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries} failed: {str(e)}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
            return None

        return wrapper

    return decorator


class EnhancedMapQuestService(MapQuestService):
    """Enhanced MapQuest service with Redis caching and fallback behavior."""

    def __init__(self):
        super().__init__()
        self.redis_client = None
        self.cache_enabled = False
        self.connect_to_redis()

    def connect_to_redis(self) -> None:
        """Attempt to connect to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=getattr(settings, "REDIS_PORT", 6379),
                db=getattr(settings, "REDIS_DB", 0),
                socket_timeout=5,
            )
            self.redis_client.ping()  # Test connection
            self.cache_enabled = True
            logger.info("Successfully connected to Redis cache")
        except redis.RedisError as e:
            logger.warning(
                f"Redis connection failed: {str(e)}. Continuing without caching."
            )
            self.cache_enabled = False

    def get_cache_key(self, address: str) -> str:
        """Generate a cache key for an address."""
        return f"geocode:{address}"

    def get_from_cache(self, address: str) -> Optional[Tuple[float, float]]:
        """Retrieve geocoding results from cache."""
        if not self.cache_enabled:
            return None

        try:
            cached = self.redis_client.get(self.get_cache_key(address))
            if cached:
                lat, lng = cached.decode().split(",")
                return float(lat), float(lng)
        except (redis.RedisError, ValueError) as e:
            logger.warning(f"Cache retrieval failed for {address}: {str(e)}")
        return None

    def save_to_cache(self, address: str, coordinates: Tuple[float, float]) -> None:
        """Save geocoding results to cache."""
        if not self.cache_enabled:
            return

        try:
            cache_key = self.get_cache_key(address)
            cache_value = f"{coordinates[0]},{coordinates[1]}"
            self.redis_client.setex(cache_key, 86400, cache_value)  # Cache for 24 hours
        except redis.RedisError as e:
            logger.warning(f"Cache save failed for {address}: {str(e)}")

    @retry_on_failure(retries=3, delay=1)
    def geocode(self, address: str) -> Tuple[float, float]:
        """Geocode an address with caching and retry logic."""
        # Try cache first
        cached_result = self.get_from_cache(address)
        if cached_result:
            return cached_result

        # Fallback to API call
        coordinates = super().geocode(address)

        # Cache successful results
        self.save_to_cache(address, coordinates)

        return coordinates


class Command(BaseCommand):
    """
    Management command to load fuel station data from CSV with enhanced error handling.
    """

    help = "Load fuel station data from CSV file with idempotency check and enhanced error handling"

    def add_arguments(self, parser) -> None:
        """Add command line arguments."""
        parser.add_argument(
            "--csv-file",
            type=str,
            default="fuel-prices-for-be-assessment.csv",
            help="Path to the CSV file containing fuel station data",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force reload data even if already present",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of records to process in each batch",
        )

    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        """Handle the command execution with enhanced error handling."""
        csv_file = options["csv_file"]
        force = options.get("force", False)
        batch_size = options.get("batch_size", 100)

        if not os.path.exists(csv_file):
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_file}"))
            return

        existing_count = FuelStation.objects.count()
        if existing_count > 0 and not force:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fuel station data already loaded ({existing_count} stations). "
                    "Use --force to reload."
                )
            )
            return

        map_quest = EnhancedMapQuestService()
        processed_ids: Set[int] = set()
        failed_records: list[dict[str, Any]] = []
        success_count = 0

        try:
            with transaction.atomic():
                with open(csv_file, "r", encoding="utf-8") as file:
                    reader = csv.dictReader(file)
                    stations_to_create = []

                    for row in reader:
                        station_id = int(row["OPIS Truckstop ID"])

                        if station_id in processed_ids:
                            continue

                        processed_ids.add(station_id)
                        address = f"{row['Address']}, {row['City']}, {row['State']}"

                        try:
                            lat, lng = map_quest.geocode(address)

                            station = FuelStation(
                                station_id=station_id,
                                name=row["Truckstop Name"],
                                address=row["Address"],
                                city=row["City"],
                                state=row["State"],
                                rack_id=int(row["Rack ID"]),
                                retail_price=Decimal(row["Retail Price"]),
                                location=Point(lng, lat),
                            )
                            stations_to_create.append(station)
                            success_count += 1

                            if len(stations_to_create) >= batch_size:
                                FuelStation.objects.bulk_create(stations_to_create)
                                self.stdout.write(
                                    f"Processed {success_count} stations..."
                                )
                                stations_to_create = []

                        except Exception as e:
                            logger.error(
                                f"Error processing station {station_id}: {str(e)}"
                            )
                            failed_records.append(
                                {
                                    "station_id": station_id,
                                    "address": address,
                                    "error": str(e),
                                }
                            )
                            continue

                    # Create remaining stations
                    if stations_to_create:
                        FuelStation.objects.bulk_create(stations_to_create)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully loaded {success_count} stations. "
                        f"Failed to process {len(failed_records)} stations."
                    )
                )

                if failed_records:
                    self.stdout.write("\nFailed records:")
                    for record in failed_records:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Station ID: {record['station_id']}, "
                                f"Address: {record['address']}, "
                                f"Error: {record['error']}"
                            )
                        )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to load fuel station data: {str(e)}")
            )
            raise
