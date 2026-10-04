# Deployment: Unraid + Nginx Proxy Manager

This guide runs BingoSync on an Unraid server with Docker Compose, behind
Nginx Proxy Manager (NPM) for HTTPS. It works the same on any Docker host with
a reverse proxy that terminates HTTPS and supports websockets.

```
players ──https──▶ NPM (TLS, Let's Encrypt) ──http──▶ <unraid-ip>:8088
                                                        │
                                              bingosync-nginx
                                         /static/  ·  /websocket/ ──▶ tornado
                                                        └── everything else ──▶ django
```

The stack is five containers: `bingosync-nginx`, `bingosync-django`,
`bingosync-tornado` (live sync), `bingosync-postgres`, and `bingosync-redis`.
Only nginx publishes a port. If you
[use your own Postgres](#using-your-own-postgres), `bingosync-postgres` isn't
started.

## 1. Install Docker Compose Manager

In the Unraid web UI, open **Apps**, search for **Docker Compose Manager**, and
install it. This adds the `docker compose` command.

## 2. Get the code onto Unraid

Open the Unraid terminal (the `>_` icon at the top right of the web UI):

```bash
mkdir -p /mnt/user/appdata/bingosync
cd /mnt/user/appdata/bingosync
git clone https://github.com/t-vaudry/bingosync.git .
```

If `git` isn't available, download the code instead:

```bash
curl -L https://github.com/t-vaudry/bingosync/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=1
```

## 3. Configure

```bash
cp .env.example .env
nano .env
```

Fill in the required values. Generate each secret with `openssl rand -hex 32`
and paste the output in:

| Variable | What to put |
|----------|-------------|
| `DOMAIN` | The public hostname, e.g. `bingo.example.com` (no `https://`) |
| `HTTP_PORT` | Port on Unraid for NPM to forward to. Default `8088`; don't use 80/443 |
| `DB_PASSWORD` | Generated secret |
| `DJANGO_SECRET_KEY` | Generated secret |
| `INTERNAL_API_SECRET` | Generated secret |

Leave `COMPOSE_PROFILES=bundled-db` in place to use the bundled database. Its
files go in `/mnt/user/appdata/bingosync/postgres-data`, so they survive the
Docker image being recreated. To use a Postgres container you already run, see
[Using your own Postgres](#using-your-own-postgres) before starting.

Optional: `SENTRY_DSN` for error reporting, and the `EMAIL_*` settings for
password-reset emails (see [Password resets](#password-resets-without-email)).

## 4. Start the stack

```bash
docker compose up -d --build
```

The first build takes a few minutes. Database migrations and static files run
automatically each time the Django container starts. Check that everything is
up:

```bash
docker compose ps
```

All the containers should be running, and `bingosync-django` should show as
healthy after about a minute. They also appear in Unraid's **Docker** tab.

## 5. Add the proxy host in Nginx Proxy Manager

1. Point a DNS record for your hostname at your home connection, the same way
   as your other NPM-proxied apps.
2. In NPM, add a **Proxy Host**:
   - **Domain Names:** your `DOMAIN`
   - **Scheme:** `http`
   - **Forward Hostname / IP:** the address you use for your other Unraid apps
     (usually the Unraid server's LAN IP)
   - **Forward Port:** your `HTTP_PORT` (default `8088`)
   - **Websockets Support:** on. Without it, boards won't update live.
3. On the **SSL** tab, request a new Let's Encrypt certificate and turn on
   **Force SSL**.

## 6. Create your admin account

```bash
docker compose exec django python manage.py createsuperuser
```

## 7. Check it works

1. Open `https://<your DOMAIN>`, log in, and create a room.
2. The room feed should say you **connected**. That means live sync works.
3. Open the room in a second browser (or a private window) as another user and
   mark a square. It should appear in the first browser without refreshing.

## Updating

```bash
cd /mnt/user/appdata/bingosync
git pull            # or re-run the curl command from step 2
docker compose up -d --build
```

Your `.env` and the database are kept. Static filenames are content-hashed, so
players get new CSS and JavaScript without a hard refresh.

## Using your own Postgres

To store BingoSync's data in a Postgres container you already run on Unraid:

1. Create a user and database for it. Replace `<your-postgres>` with that
   container's name, and choose a password:

   ```bash
   docker exec -it <your-postgres> psql -U postgres \
     -c "CREATE USER bingosync WITH PASSWORD '<password>';" \
     -c "CREATE DATABASE bingosync OWNER bingosync;"
   ```

2. In `.env`, delete the `COMPOSE_PROFILES=bundled-db` line and set:

   ```bash
   DB_HOST=<unraid-lan-ip>
   DB_PORT=<port your Postgres container publishes, usually 5432>
   DB_NAME=bingosync
   DB_USER=bingosync
   DB_PASSWORD=<password>
   ```

3. Run `docker compose up -d --build`. The tables are created on first start.

If you switch an existing install over, `bingosync-postgres` keeps running
until you remove it with `docker compose rm -sf postgres`. Its data stays in
`postgres-data` until you delete that folder.

## Backups

With the bundled database, the data files are in
`/mnt/user/appdata/bingosync/postgres-data`. They survive the Docker image
being recreated. Copying them while Postgres is running doesn't give a
consistent backup, though, so take a dump as well:

```bash
cd /mnt/user/appdata/bingosync
mkdir -p backups
docker compose exec -T postgres pg_dump -U bingosync bingosync \
  | gzip > backups/db_$(date +%Y%m%d_%H%M%S).sql.gz
```

Restore a dump:

```bash
gunzip < backups/<file>.sql.gz \
  | docker compose exec -T postgres psql -U bingosync bingosync
```

To run the dump on a schedule, the **User Scripts** plugin can run the dump
commands daily. Take one before every tournament. If you use your own
Postgres, back it up the way you already do for that container.

## Password resets without email

Without `EMAIL_HOST`, password-reset emails aren't sent. The full email,
including the reset link, is written to the Django log instead:

```bash
docker compose logs --tail=100 django
```

Copy the link to the player. To send real emails, fill in the `EMAIL_*`
settings in `.env` and run `docker compose up -d`.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Bad Request (400)` on every page | `DOMAIN` in `.env` doesn't match the hostname in the browser |
| "Too many redirects" | NPM is forwarding to the wrong port; it must point at `HTTP_PORT` |
| Room feed never says "connected"; marks only show after refresh | **Websockets Support** is off in the NPM proxy host |
| `docker compose up` stops with "Set … in .env" | A required value in `.env` is empty |
| `bingosync-django` keeps restarting; log says "PostgreSQL … is not reachable" | Bundled: `COMPOSE_PROFILES=bundled-db` is missing from `.env`. Your own: `DB_HOST`/`DB_PORT` are wrong |
| Port already in use | Something else uses `HTTP_PORT`; pick another port and update NPM |

Logs:

```bash
docker compose logs -f django
docker compose logs -f tornado
docker compose logs -f nginx
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOMAIN` | Yes | – | Public hostname; also used for allowed hosts, CSRF, and the websocket URL |
| `DB_PASSWORD` | Yes | – | PostgreSQL password |
| `DJANGO_SECRET_KEY` | Yes | – | Django secret key |
| `INTERNAL_API_SECRET` | Yes | – | Shared secret between Django and the websocket server (32+ characters) |
| `HTTP_PORT` | No | `8088` | Host port nginx listens on |
| `COMPOSE_PROFILES` | No | – | `bundled-db` runs the bundled Postgres; remove it to use your own |
| `POSTGRES_DATA_DIR` | No | `./postgres-data` | Where the bundled Postgres stores its files |
| `DB_HOST` | No | `postgres` (bundled) | Postgres server to connect to |
| `DB_PORT` | No | `5432` | Postgres port |
| `DB_NAME` | No | `bingosync` | Database name |
| `DB_USER` | No | `bingosync` | PostgreSQL user |
| `DEBUG` | No | `0` | Must stay `0` in production |
| `DJANGO_LOG_LEVEL` | No | `INFO` | Logging level |
| `SENTRY_DSN` | No | – | Sentry error reporting |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | No | – | SMTP for password-reset emails |
