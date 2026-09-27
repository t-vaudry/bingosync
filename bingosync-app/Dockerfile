# Multi-stage build for Django application
# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set work directory
WORKDIR /app

# Copy dependency file
COPY pyproject.toml /app/

# Install dependencies using uv
RUN uv pip install --system -r pyproject.toml && \
    uv pip install --system gunicorn

# Stage 2: Runtime - Create minimal production image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    bash \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN groupadd -r django && useradd -r -g django django

# Set work directory
WORKDIR /app

# Copy entrypoint script
COPY --chown=django:django docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Copy application code
COPY --chown=django:django . /app/

# Create directories and set permissions
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app/staticfiles /app/media && \
    chmod -R 775 /app/generators && \
    chown -R django:django /app/generators

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run Gunicorn with 4 workers
CMD ["gunicorn", "bingosync.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--enable-stdio-inheritance"]
