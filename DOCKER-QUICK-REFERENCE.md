# Docker Quick Reference

This guide covers both development and production Docker Compose setups.

## Development Setup

### Initial Setup
```bash
./dev-setup.sh
```

## Start/Stop
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Stop all services
docker-compose -f docker-compose.dev.yml down

# Restart a service
docker-compose -f docker-compose.dev.yml restart django
```

## Logs
```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f django
```

## Django Commands
```bash
# Migrations
docker-compose -f docker-compose.dev.yml exec django python manage.py migrate
docker-compose -f docker-compose.dev.yml exec django python manage.py makemigrations

# Shell
docker-compose -f docker-compose.dev.yml exec django python manage.py shell

# Create superuser
docker-compose -f docker-compose.dev.yml exec django python manage.py createsuperuser

# Tests
docker-compose -f docker-compose.dev.yml exec django python manage.py test
```

## Database
```bash
# PostgreSQL shell
docker-compose -f docker-compose.dev.yml exec postgres psql -U bingosync -d bingosync

# Reset database (WARNING: destroys data)
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d postgres
docker-compose -f docker-compose.dev.yml exec django python manage.py migrate
```

## Rebuild
```bash
# After changing requirements.txt or Dockerfile
docker-compose -f docker-compose.dev.yml build
docker-compose -f docker-compose.dev.yml up -d
```

## Access Points
- Django: http://localhost:8000
- Admin: http://localhost:8000/admin
- PostgreSQL: localhost:5432 (user: bingosync, pass: bingosync_dev_password)
- Redis: localhost:6379
- WebSocket: ws://localhost:8888

---

## Production Deployment

For the full walkthrough (Unraid + Nginx Proxy Manager), see
[DEPLOYMENT.md](DEPLOYMENT.md).

### Prerequisites
1. Docker and Docker Compose installed
2. A domain name pointing at your reverse proxy
3. A reverse proxy that terminates HTTPS (e.g. Nginx Proxy Manager) and
   forwards to this stack's `HTTP_PORT` with websocket support enabled

### Initial Production Setup

1. **Copy and configure environment variables:**
```bash
cp .env.example .env
nano .env  # Edit with your production values
```

2. **Fill in the required values in .env:**
```bash
# Generate each secret with:
openssl rand -hex 32

DOMAIN=bingo.yourdomain.com
HTTP_PORT=8088
DB_USER=bingosync
DB_PASSWORD=<generated>
DJANGO_SECRET_KEY=<generated>
INTERNAL_API_SECRET=<generated>
```

3. **Build and start services** (migrations and static files run automatically
   when the Django container starts):
```bash
docker compose up -d --build
```

4. **Create superuser:**
```bash
docker compose exec django python manage.py createsuperuser
```

### Production Commands

#### Start/Stop Services
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a service
docker-compose restart django
```

#### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f django
docker-compose logs -f nginx
```

#### Database Management
```bash
# Run migrations
docker-compose exec django python manage.py migrate

# Create database backup
docker-compose exec postgres pg_dump -U $DB_USER bingosync > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore database backup
docker-compose exec -T postgres psql -U $DB_USER bingosync < backup.sql
```

#### Updates and Maintenance
```bash
# Pull latest code
git pull

# Rebuild and restart services
docker-compose build
docker-compose up -d

# Run migrations after code update
docker-compose exec django python manage.py migrate

# Collect static files after code update
docker-compose exec django python manage.py collectstatic --noinput
```

#### Health Checks
```bash
# Check service status
docker-compose ps

# Check Django health
curl http://localhost/health

# Check logs for errors
docker-compose logs --tail=100 django
docker-compose logs --tail=100 tornado
```

### Production Monitoring

#### View Resource Usage
```bash
# Container stats
docker stats

# Disk usage
docker system df
```

#### Clean Up
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (WARNING: may delete data)
docker volume prune
```

### Troubleshooting

#### Services won't start
```bash
# Check logs
docker-compose logs

# Check if the HTTP port is already in use (default 8088)
netstat -tulpn | grep -E ':8088'

# Verify environment variables
docker-compose config
```

#### Database connection issues
```bash
# Check PostgreSQL health
docker-compose exec postgres pg_isready -U $DB_USER

# Check database logs
docker-compose logs postgres
```

#### WebSocket connection issues
```bash
# Check Tornado logs
docker-compose logs tornado

# Verify nginx WebSocket configuration
docker-compose exec nginx nginx -t
```

### Security Checklist

Before deploying to production, ensure:
- [ ] DEBUG=0 in .env
- [ ] Strong DJANGO_SECRET_KEY generated
- [ ] Strong INTERNAL_API_SECRET generated (32+ characters)
- [ ] Strong DB_PASSWORD set
- [ ] DOMAIN set to the public hostname
- [ ] Reverse proxy serves DOMAIN over HTTPS with websocket support enabled
- [ ] HTTP_PORT only reachable from the reverse proxy / LAN, not the internet
- [ ] Regular database backups scheduled
- [ ] Sentry or error monitoring configured (optional)
- [ ] Log rotation configured

### Backup Strategy

#### Automated Daily Backups
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U $DB_USER bingosync | gzip > $BACKUP_DIR/bingosync_$DATE.sql.gz
# Keep only last 30 days
find $BACKUP_DIR -name "bingosync_*.sql.gz" -mtime +30 -delete
EOF

chmod +x backup.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /path/to/backup.sh" | crontab -
```
