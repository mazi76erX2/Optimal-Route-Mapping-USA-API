#!/bin/sh

# Chack if database has started
if [ "$DATABASE" = $DATABASE_NAME ]
then
    echo "Waiting for postgres..."

    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi