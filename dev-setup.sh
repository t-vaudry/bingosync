#!/bin/bash

set -e

echo "🚀 Bingosync Development Environment Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed."
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed."
    echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

# Use 'docker compose' or 'docker-compose' depending on what's available
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env file exists, if not copy from .env.example
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created. You can edit it to customize your configuration."
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Stop any running containers
echo "🛑 Stopping any running containers..."
$DOCKER_COMPOSE -f docker-compose.dev.yml down 2>/dev/null || true
echo ""

# Build and start containers
echo "🏗️  Building Docker images..."
$DOCKER_COMPOSE -f docker-compose.dev.yml build
echo ""

echo "🚀 Starting services..."
$DOCKER_COMPOSE -f docker-compose.dev.yml up -d postgres redis
echo ""

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if $DOCKER_COMPOSE -f docker-compose.dev.yml exec -T postgres pg_isready -U bingosync &> /dev/null; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start in time"
        exit 1
    fi
    sleep 1
done
echo ""

# Build Django container
echo "🏗️  Building Django application..."
$DOCKER_COMPOSE -f docker-compose.dev.yml build django
echo ""

# Run migrations
echo "🔄 Running database migrations..."
$DOCKER_COMPOSE -f docker-compose.dev.yml run --rm django python manage.py migrate
echo ""

# Create superuser
echo "👤 Create a Django superuser account"
echo "You'll be prompted for username, email, and password:"
echo ""
$DOCKER_COMPOSE -f docker-compose.dev.yml run --rm django python manage.py createsuperuser || {
    echo ""
    echo "⚠️  Superuser creation skipped or failed. You can create one later with:"
    echo "   $DOCKER_COMPOSE -f docker-compose.dev.yml run --rm django python manage.py createsuperuser"
    echo ""
}

# Start all services
echo "🚀 Starting all services..."
$DOCKER_COMPOSE -f docker-compose.dev.yml up -d
echo ""

# Show status
echo "📊 Service Status:"
$DOCKER_COMPOSE -f docker-compose.dev.yml ps
echo ""

echo "✅ Development environment is ready!"
echo ""
echo "📝 Next Steps:"
echo "   • Django app: http://localhost:8000"
echo "   • Django admin: http://localhost:8000/admin"
echo "   • WebSocket server: ws://localhost:8888"
echo ""
echo "🔧 Useful Commands:"
echo "   • View logs: $DOCKER_COMPOSE -f docker-compose.dev.yml logs -f"
echo "   • Stop services: $DOCKER_COMPOSE -f docker-compose.dev.yml down"
echo "   • Restart services: $DOCKER_COMPOSE -f docker-compose.dev.yml restart"
echo "   • Run Django shell: $DOCKER_COMPOSE -f docker-compose.dev.yml exec django python manage.py shell"
echo "   • Run tests: $DOCKER_COMPOSE -f docker-compose.dev.yml exec django python manage.py test"
echo ""
echo "📖 See README-DEV.md for more information"
