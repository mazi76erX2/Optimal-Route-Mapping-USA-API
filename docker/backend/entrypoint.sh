#!/bin/sh

# Exit on error
set -e

# Function to wait for a service
wait_for_service() {
    local host="$1"
    local port="$2"
    local service="$3"
    
    echo "Waiting for $service..."
    while ! nc -z $host $port; do
        sleep 0.1
    done
    echo "$service started"
}

# Wait for PostgreSQL
if [ "$DATABASE_NAME" = "optimal-mapping" ]; then
    wait_for_service $DATABASE_HOST $DATABASE_PORT "PostgreSQL"
fi

# Wait for Redis
wait_for_service "redis" 6379 "Redis"

# Change to application directory
cd /app/backend

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Load fuel station data if needed
echo "Checking and loading fuel station data..."
python manage.py import_stations --csv-file /app/backend/fuel-prices-for-be-assessment.csv

# Create cache table
echo "Setting up cache table..."
python manage.py createcachetable

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the application
echo "Starting application..."
exec "$@"