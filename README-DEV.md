# Bingosync Development Environment

Docker-based development environment for Bingosync. We use `pyproject.toml` with `uv` for fast dependency management.

## Prerequisites

- **Docker Desktop** (includes Docker Compose)
  - [Download for Windows/Mac](https://docs.docker.com/get-docker/)

Verify installation:
```bash
docker --version
docker compose version
```

## Quick Start

1. **Create environment file**:
   ```bash
   copy .env.example .env
   ```

2. **Build and start services**:
   ```bash
   docker compose -f docker-compose.dev.yml up -d --build
   ```

3. **Run migrations**:
   ```bash
   docker compose -f docker-compose.dev.yml exec django python manage.py migrate
   ```

4. **Create superuser**:
   ```bash
   docker compose -f docker-compose.dev.yml exec django python manage.py createsuperuser
   ```

5. **Access the application**:
   - Django app: http://localhost:8000
   - Django admin: http://localhost:8000/admin
   - WebSocket server: ws://localhost:8888

## Services

The development environment includes:

- **PostgreSQL 15**: Database server (port 5432)
- **Redis 7**: Cache and message broker (port 6379)
- **Django**: Web application (port 8000)
- **Tornado WebSocket**: Real-time communication server (port 8888)

## Common Commands

### Starting and Stopping

```bash
# Start all services
docker compose -f docker-compose.dev.yml up -d

# Stop all services
docker compose -f docker-compose.dev.yml down

# Restart a specific service
docker compose -f docker-compose.dev.yml restart django

# Stop and remove all containers, volumes, and images
docker compose -f docker-compose.dev.yml down -v
```

### Viewing Logs

```bash
# View logs from all services
docker compose -f docker-compose.dev.yml logs -f

# View logs from a specific service
docker compose -f docker-compose.dev.yml logs -f django

# View last 100 lines
docker compose -f docker-compose.dev.yml logs --tail=100 django
```

### Database Operations

```bash
# Run migrations
docker compose -f docker-compose.dev.yml exec django python manage.py migrate

# Create migrations
docker compose -f docker-compose.dev.yml exec django python manage.py makemigrations

# Create a superuser
docker compose -f docker-compose.dev.yml exec django python manage.py createsuperuser

# Access PostgreSQL shell
docker compose -f docker-compose.dev.yml exec postgres psql -U bingosync -d bingosync

# Reset database (WARNING: destroys all data)
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d postgres
docker compose -f docker-compose.dev.yml exec django python manage.py migrate
```

### Django Management

```bash
# Django shell
docker compose -f docker-compose.dev.yml exec django python manage.py shell

# Collect static files
docker compose -f docker-compose.dev.yml exec django python manage.py collectstatic --noinput

# Run a custom management command
docker compose -f docker-compose.dev.yml exec django python manage.py <command>
```

### Running Tests

```bash
# Run all tests
docker compose -f docker-compose.dev.yml exec django python manage.py test

# Run specific test file
docker compose -f docker-compose.dev.yml exec django python manage.py test bingosync.tests.test_views

# Run with verbose output
docker compose -f docker-compose.dev.yml exec django python manage.py test --verbosity=2

# Run tests in parallel
docker compose -f docker-compose.dev.yml exec django python manage.py test --parallel
```

### Rebuilding Containers

If you modify `pyproject.toml` or Dockerfiles:

```bash
# Rebuild all images
docker compose -f docker-compose.dev.yml build

# Rebuild a specific service
docker compose -f docker-compose.dev.yml build django

# Rebuild without cache
docker compose -f docker-compose.dev.yml build --no-cache

# Rebuild and restart
docker compose -f docker-compose.dev.yml up -d --build
```

## Environment Configuration

The `.env` file contains all environment variables. Key settings:

- `DEBUG=1`: Enable Django debug mode
- `SECRET_KEY`: Django secret key (change for production)
- `DATABASE_URL`: PostgreSQL connection string (required)
- `DJANGO_LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)

To modify settings:
1. Edit `.env` file
2. Restart the affected service: `docker compose -f docker-compose.dev.yml restart django`

## Troubleshooting

### Port Already in Use

If you see "port is already allocated" errors:

```bash
# Check what's using the port (example for port 8000)
netstat -ano | findstr :8000  # Windows

# Stop the conflicting service or change the port in docker-compose.dev.yml
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.dev.yml ps postgres

# Check PostgreSQL logs
docker compose -f docker-compose.dev.yml logs postgres

# Restart PostgreSQL
docker compose -f docker-compose.dev.yml restart postgres

# Wait for PostgreSQL to be ready
docker compose -f docker-compose.dev.yml exec postgres pg_isready -U bingosync
```

### Container Keeps Restarting

```bash
# Check container logs for errors
docker compose -f docker-compose.dev.yml logs django

# Check container status
docker compose -f docker-compose.dev.yml ps

# Inspect container
docker inspect bingosync-django
```

### Clean Slate Reset

If things are completely broken:

```bash
# Stop everything and remove volumes
docker compose -f docker-compose.dev.yml down -v

# Remove all related images
docker images | findstr bingosync

# Start fresh
docker compose -f docker-compose.dev.yml up -d --build
```

### Python Package Issues

If you need to install additional packages:

1. Add to `pyproject.toml` under `dependencies`
2. Rebuild the container:
   ```bash
   docker compose -f docker-compose.dev.yml build django
   docker compose -f docker-compose.dev.yml up -d django
   ```

We use `uv` for fast dependency installation (10-100x faster than pip).

## Development Workflow

1. **Make code changes**: Edit files in `bingosync-app/` or `bingosync-websocket/`
2. **Changes auto-reload**: Django's development server will automatically reload
3. **View logs**: `docker compose -f docker-compose.dev.yml logs -f django`
4. **Run tests**: `docker compose -f docker-compose.dev.yml exec django python manage.py test`
5. **Commit changes**: Use git as normal

## Accessing Services from Host

All services are accessible from your host machine:

- Django: `http://localhost:8000`
- PostgreSQL: `localhost:5432` (user: `bingosync`, password: `bingosync_dev_password`, db: `bingosync`)
- Redis: `localhost:6379`
- WebSocket: `ws://localhost:8888`

You can connect to PostgreSQL using any database client (pgAdmin, DBeaver, etc.).

## Production Considerations

This setup is for **development only**. For production:

- Use strong passwords and secrets
- Set `DEBUG=0`
- Use proper SSL/TLS certificates
- Configure proper logging and monitoring
- Use production-grade WSGI server (gunicorn, uwsgi)
- Set up proper backup strategies
- Use environment-specific configuration

## Getting Help

- Check the logs: `docker-compose -f docker-compose.dev.yml logs`
- Verify service health: `docker-compose -f docker-compose.dev.yml ps`
- Review Django documentation: https://docs.djangoproject.com/
- Review Docker documentation: https://docs.docker.com/

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Tornado Documentation](https://www.tornadoweb.org/)
