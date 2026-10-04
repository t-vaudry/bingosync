#!/bin/bash
set -e

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
# Deadline by the clock: a check against a host that doesn't exist can take
# several seconds on its own (name lookup).
deadline=$((SECONDS + 60))
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "${DB_USER:-bingosync}" -t 3 > /dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "PostgreSQL at ${DB_HOST}:${DB_PORT} is not reachable after 60 seconds." >&2
    echo "Bundled database: check that .env contains COMPOSE_PROFILES=bundled-db." >&2
    echo "Your own database: check DB_HOST and DB_PORT in .env." >&2
    exit 1
  fi
  sleep 1
done
echo "PostgreSQL started"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting server..."
exec "$@"
