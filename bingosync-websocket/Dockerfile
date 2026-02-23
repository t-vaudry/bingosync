# Production Dockerfile for Tornado WebSocket Server
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WS_PORT=8888

# Create non-root user
RUN groupadd -r tornado && useradd -r -g tornado tornado

# Set work directory
WORKDIR /app

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install \
    tornado~=6.2 \
    redis \
    requests \
    requests-unixsocket

# Copy application files
COPY --chown=tornado:tornado app.py /app/

# Switch to non-root user
USER tornado

# Expose WebSocket port
EXPOSE 8888

# Health check - verify the server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888').read()" || exit 1

# Run the application
CMD ["python", "app.py"]
