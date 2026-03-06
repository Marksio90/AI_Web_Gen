# Docker Deployment Guide

## Stack Architecture

```
Internet
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  NGINX (port 80)  / Traefik (443, prod)                          │
│  Routes:                                                          │
│   :80   → platform:3000    (Next.js)                             │
│   :8001 → agents:8000      (FastAPI)                             │
│   :5556 → flower:5555      (Celery Monitor)                      │
│   :8082 → adminer:8080     (DB Admin)                            │
└────────┬──────────────────────────────────────────────────────────┘
         │  frontend network
    ┌────┴────┬─────────────┬──────────┬──────────┐
    │         │             │          │          │
    ▼         ▼             ▼          ▼          ▼
platform  agents        flower     adminer   redis-commander
:3000     :8000         :5555      :8080      :8081 (dev only)
    │         │
    │  backend network (internal — no external access)
    ├─────────┼──────────────────────────────────────────┐
    │         │                                          │
    ▼         ▼                                          ▼
postgres    redis ←───── worker (4 concurrent) ────── beat
:5432       :6379          (pipeline tasks)         (scheduler)
```

## Service Summary

| Service | Image | Purpose | Memory |
|---------|-------|---------|--------|
| `postgres` | postgres:17-alpine | Database | 512M |
| `redis` | redis:7-alpine | Broker + cache | 256M |
| `platform` | custom (Next.js 15) | Admin dashboard + API | 512M |
| `agents` | custom (Python 3.12) | FastAPI agent pipeline | 1G |
| `worker` | custom (Celery) | Background task execution | 2G |
| `beat` | custom (Celery Beat) | Scheduled tasks | 128M |
| `flower` | custom | Celery monitoring UI | 256M |
| `nginx` | nginx:1.27-alpine | Reverse proxy | 64M |
| `adminer` | adminer:4 | DB web admin | 64M |
| `redis-commander` | rediscommander (dev) | Redis browser | 128M |

**Total: ~5GB RAM recommended** (3GB minimum)

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/yourname/ai-web-gen
cd ai-web-gen
make setup       # creates .env from template + directories

# 2. Fill in required env vars
nano .env        # minimum: OPENAI_API_KEY, POSTGRES_PASSWORD, AUTH_SECRET

# 3. Start everything
make up          # builds images + starts all 10 services

# 4. Verify
make health      # checks all endpoints

# 5. Open
open http://localhost          # Platform
open http://localhost:8001/docs # FastAPI docs
open http://localhost:5556      # Celery Flower
```

## Common Operations

### Start/Stop
```bash
make up           # start dev stack
make down         # stop (keep data)
make restart      # restart all
make restart-platform  # restart just one service
make down-all     # stop + delete volumes (data loss!)
```

### Logs
```bash
make logs              # all services
make logs-f platform   # just Next.js
make logs-f agents     # just FastAPI
make logs-f worker     # just Celery worker
```

### Shells
```bash
make shell-platform  # Next.js bash
make shell-agents    # Python bash
make shell-db        # psql
make shell-redis     # redis-cli
```

### Business Discovery
```bash
# Discover restaurants in Warsaw (default)
make crawl

# Custom city + category
make crawl CITY=Kraków CATEGORY=beauty_salon LIMIT=500

# Full Poland sweep (all major cities × top categories)
make crawl-all

# Process discovered leads through AI pipeline
make process-leads
```

### Database
```bash
make db-migrate     # apply schema changes
make db-seed        # insert demo data
make db-reset       # drop + recreate (DEV only!)
make db-backup      # create SQL.gz backup
make db-studio      # open Prisma Studio visual editor
```

### Celery Tasks
```bash
make celery-status  # show active tasks
make celery-purge   # clear all queued tasks
make celery-scale N=4  # scale to 4 worker replicas
```

## Production Deployment

```bash
# 1. Set production env vars
nano .env
# Set: DOMAIN, ACME_EMAIL, strong passwords, real API keys

# 2. Generate htpasswd for Flower
echo "admin:$(openssl passwd -apr1 yourpassword)" >> .env
# Add to .env: FLOWER_BASIC_AUTH_TRAEFIK=admin:$apr1$...

# 3. Start production stack
make prod

# Traefik auto-obtains Let's Encrypt certificates
# Access at: https://yourplatform.pl
```

## Network Isolation

The stack uses two Docker networks:
- **frontend** — external-facing; nginx, platform, agents, flower, adminer
- **backend** — internal only (`internal: true`); postgres, redis, worker, beat

PostgreSQL and Redis are **not** accessible from outside Docker without explicit port mapping. In production (`docker-compose.prod.yml`), all direct port bindings are removed — only Traefik handles external traffic.

## Data Persistence

```
volumes:
  postgres_data  →  /var/lib/postgresql/data  (all CRM data)
  redis_data     →  /data                     (task queue state)
  traefik_certs  →  /letsencrypt              (prod: TLS certs)
```

To backup:
```bash
make db-backup   # → backups/aiwebgen_TIMESTAMP.sql.gz
```

## Scheduled Tasks (Celery Beat)

Beat runs two automatic schedules:

| Schedule | Task | When |
|----------|------|------|
| `nightly-discovery` | Crawl 5 cities × 4 categories | Every 24h (02:00 Warsaw) |
| `process-pending-leads` | Run AI pipeline for new leads | Every 6h |

Customize in `agents/tasks.py` → `beat_schedule`.

## Troubleshooting

### Platform won't start
```bash
docker logs aiwebgen-platform
# Usually: DB connection error or missing env var
make db-migrate  # apply schema if DB is new
```

### Agent pipeline errors
```bash
docker logs aiwebgen-agents
# Check: OPENAI_API_KEY valid, REDIS_URL reachable
make shell-agents
python -c "from config import settings; print(settings.openai_api_key[:10])"
```

### Celery tasks stuck
```bash
make celery-status  # see what's running
open http://localhost:5556  # Flower UI
make celery-purge  # nuclear option: clear queue
```

### Out of disk space
```bash
make clean-all    # remove unused Docker objects
make db-backup    # backup first!
docker volume ls  # check volume sizes
```
