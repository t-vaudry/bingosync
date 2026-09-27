#!/bin/bash
set -e

echo "Waiting for postgres..."
while ! pg_isready -h postgres -U ${DB_USER:-bingosync} > /dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL started"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting server..."
exec "$@"
