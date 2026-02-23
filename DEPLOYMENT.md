# HP Bingo Platform - Deployment Guide

This guide covers deploying the HP Bingo Platform using Docker Compose.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### System Requirements
- **Minimum**: 2 CPU cores, 4GB RAM, 20GB disk
- **Recommended**: 4 CPU cores, 8GB RAM, 50GB disk

### Domain & SSL (Production)
- Domain name pointing to your server
- SSL certificate (Let's Encrypt recommended)

## Quick Start

For local testing or development:

```bash
# 1. Clone the repository
git clone <repository-url>
cd bingosync

# 2. Copy environment file
cp .env.example .env

# 3. Start services
docker-compose up -d

# 4. Run migrations
docker-compose exec django python manage.py migrate

# 5. Create admin user
docker-compose exec django python manage.py createsuperuser

# 6. Access the platform
# Open http://localhost in your browser
```

## Production Deployment

### Step 1: Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd bingosync

# Copy and edit environment file
cp .env.example .env
nano .env
```

### Step 3: Configure Environment Variables

Edit `.env` with production values:

```bash
# Database credentials
DB_USER=bingosync
DB_PASSWORD=<generate-strong-password>

# Django settings
DJANGO_SECRET_KEY=<generate-secret-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DEBUG=0

# Internal API security
INTERNAL_API_SECRET=<generate-32-char-secret>

# WebSocket
SOCKETS_DOMAIN=tornado:8888

# Redis
REDIS_URL=redis://redis:6379/0
```

**Generate secrets:**
```bash
# Django secret key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Internal API secret
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Step 4: SSL Configuration (Recommended)

```bash
# Create SSL directory
mkdir -p ssl

# Option A: Let's Encrypt (recommended)
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem

# Option B: Self-signed (testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem
```

Edit `nginx.conf` to enable HTTPS:
- Uncomment the HTTPS server block
- Update `server_name` with your domain

### Step 5: Deploy

```bash
# Build and start services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Run database migrations
docker-compose exec django python manage.py migrate

# Collect static files
docker-compose exec django python manage.py collectstatic --noinput

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Load initial data (optional)
docker-compose exec django python manage.py loaddata achievements
```

### Step 6: Verify Deployment

```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs -f

# Test endpoints
curl http://localhost/health
curl http://yourdomain.com
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_USER` | Yes | - | PostgreSQL username |
| `DB_PASSWORD` | Yes | - | PostgreSQL password |
| `DJANGO_SECRET_KEY` | Yes | - | Django secret key |
| `ALLOWED_HOSTS` | Yes | - | Comma-separated list of allowed domains |
| `INTERNAL_API_SECRET` | Yes | - | Shared secret for Django-Tornado auth |
| `DEBUG` | No | 0 | Debug mode (0=off, 1=on) |
| `DJANGO_LOG_LEVEL` | No | INFO | Logging level |
| `SOCKETS_DOMAIN` | No | tornado:8888 | WebSocket server address |
| `REDIS_URL` | No | redis://redis:6379/0 | Redis connection URL |
| `SENTRY_DSN` | No | - | Sentry error tracking DSN |

### Service Ports

| Service | Internal Port | External Port | Description |
|---------|--------------|---------------|-------------|
| Nginx | 80, 443 | 80, 443 | HTTP/HTTPS entry point |
| Django | 8000 | - | Django application (internal) |
| Tornado | 8888 | - | WebSocket server (internal) |
| PostgreSQL | 5432 | - | Database (internal) |
| Redis | 6379 | - | Cache (internal) |

### Volumes

| Volume | Purpose | Backup Priority |
|--------|---------|-----------------|
| `postgres_data` | Database storage | **Critical** |
| `redis_data` | Cache persistence | Low |
| `static_files` | Static assets | Low (regenerable) |
| `media_files` | User uploads | High |

## Maintenance

### Updates

```bash
# Pull latest code
git pull

# Rebuild services
docker-compose build

# Restart with new code
docker-compose up -d

# Run migrations
docker-compose exec django python manage.py migrate

# Collect static files
docker-compose exec django python manage.py collectstatic --noinput
```

### Backups

#### Database Backup
```bash
# Manual backup
docker-compose exec -T postgres pg_dump -U $DB_USER bingosync | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore backup
gunzip < backup.sql.gz | docker-compose exec -T postgres psql -U $DB_USER bingosync
```

#### Automated Backups
```bash
# Create backup script
cat > /usr/local/bin/backup-bingosync.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/bingosync"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cd /path/to/bingosync
docker-compose exec -T postgres pg_dump -U $DB_USER bingosync | gzip > $BACKUP_DIR/db_$DATE.sql.gz
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup-bingosync.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /usr/local/bin/backup-bingosync.sh" | crontab -
```

### Monitoring

#### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f django
docker-compose logs -f tornado
docker-compose logs -f nginx

# Last 100 lines
docker-compose logs --tail=100 django
```

#### Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df
docker volume ls
```

#### Health Checks
```bash
# Service status
docker-compose ps

# Database health
docker-compose exec postgres pg_isready -U $DB_USER

# Redis health
docker-compose exec redis redis-cli ping

# Application health
curl http://localhost/health
```

### Scaling

```bash
# Scale Django workers
docker-compose up -d --scale django=3

# Scale Tornado workers
docker-compose up -d --scale tornado=2
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Check if ports are in use
sudo netstat -tulpn | grep -E ':(80|443|5432|6379)'

# Verify configuration
docker-compose config

# Check disk space
df -h
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker-compose ps postgres
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready -U $DB_USER

# Check environment variables
docker-compose exec django env | grep DATABASE_URL
```

### WebSocket Connection Issues

```bash
# Check Tornado logs
docker-compose logs tornado

# Verify nginx configuration
docker-compose exec nginx nginx -t

# Test WebSocket endpoint
wscat -c ws://localhost/websocket/test-room-uuid
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check database connections
docker-compose exec postgres psql -U $DB_USER -d bingosync -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis memory
docker-compose exec redis redis-cli INFO memory

# Optimize database
docker-compose exec django python manage.py dbshell
VACUUM ANALYZE;
```

### SSL Certificate Issues

```bash
# Verify certificate files
ls -la ssl/

# Test SSL configuration
docker-compose exec nginx nginx -t

# Check certificate expiration
openssl x509 -in ssl/cert.pem -noout -dates

# Renew Let's Encrypt certificate
sudo certbot renew
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
docker-compose restart nginx
```

## Security Checklist

Before going to production:

- [ ] `DEBUG=0` in `.env`
- [ ] Strong `DJANGO_SECRET_KEY` generated
- [ ] Strong `INTERNAL_API_SECRET` generated (32+ characters)
- [ ] Strong `DB_PASSWORD` set
- [ ] `ALLOWED_HOSTS` configured with actual domain(s)
- [ ] SSL certificates configured
- [ ] Firewall configured (only ports 80, 443 open)
- [ ] Regular database backups scheduled
- [ ] Log rotation configured
- [ ] Sentry or error monitoring configured (optional)
- [ ] Security headers enabled in nginx
- [ ] Rate limiting configured
- [ ] CSRF protection enabled

## Support

For issues and questions:
- Check logs: `docker-compose logs`
- Review documentation: `README.md`, `DOCKER-QUICK-REFERENCE.md`
- Check GitHub issues: <repository-url>/issues

## License

See LICENSE file for details.
