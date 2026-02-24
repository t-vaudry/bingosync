# Local Development Without Docker

Run Bingosync locally using `uv` for fast dependency management.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- [uv](https://docs.astral.sh/uv/)

## Installing uv

```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

## Setup

### 1. Install Dependencies

```bash
uv pip install -r pyproject.toml
```

### 2. Start Databases

Option A - Use Docker for just the databases:
```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=bingosync_dev_password -e POSTGRES_USER=bingosync -e POSTGRES_DB=bingosync postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine
```

Option B - Install PostgreSQL and Redis locally on Windows

### 3. Configure Environment

```bash
copy .env.example .env
# Edit .env and set DATABASE_URL
```

### 4. Run Migrations

```bash
cd bingosync-app
python manage.py migrate
python manage.py createsuperuser
```

### 5. Start Servers

Terminal 1 - Django:
```bash
cd bingosync-app
python manage.py runserver
```

Terminal 2 - WebSocket:
```bash
cd bingosync-websocket
python app.py
```

## Common Tasks

### Adding Dependencies

```bash
# Edit pyproject.toml, then:
uv pip install -r pyproject.toml
```

### Running Tests

```bash
cd bingosync-app
python manage.py test
```

### Database Management

```bash
cd bingosync-app
python manage.py makemigrations
python manage.py migrate
python manage.py shell
```

## Why uv?

- **10-100x faster** than pip
- **Simpler** than Poetry
- **Standard** pyproject.toml format
- **Cross-platform** - works on Windows, Mac, Linux

## Troubleshooting

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :8000
# Kill the process or use different port
python manage.py runserver 8001
```

### Database Connection Issues

Check PostgreSQL is running and DATABASE_URL in .env is correct.

### Module Not Found

```bash
uv pip install -r pyproject.toml
```
