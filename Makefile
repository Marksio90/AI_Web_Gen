################################################################################
# AI Web Generator — Makefile
# Single entry point for all development and production operations
#
# Usage:
#   make          → show this help
#   make up       → start full stack (dev mode)
#   make prod     → start full stack (production mode)
#   make down     → stop everything
#   make logs     → follow all logs
#   make crawl    → discover businesses
################################################################################

.DEFAULT_GOAL := help
.PHONY: help up dev prod down restart build pull logs logs-f status health \
        shell-platform shell-agents shell-db shell-redis \
        crawl crawl-all process-leads \
        db-migrate db-seed db-reset db-backup db-restore \
        test-platform test-agents \
        clean clean-all

# ─── Configuration ────────────────────────────────────────────────────────────
COMPOSE        := docker compose
COMPOSE_DEV    := $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD   := $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_TOOLS  := $(COMPOSE) --profile tools

# Crawler defaults (override with: make crawl CITY=Kraków CATEGORY=dentist)
CITY     ?= Warsaw
CATEGORY ?= restaurant
SOURCE   ?= both
LIMIT    ?= 200

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "\033[1;34m AI Web Generator — Available Commands\033[0m"
	@echo ""
	@echo "\033[1m STACK MANAGEMENT\033[0m"
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z0-9_-]+:.*##/{printf "  \033[36m%-22s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "\033[1m EXAMPLES\033[0m"
	@echo "  make crawl CITY=Kraków CATEGORY=beauty_salon LIMIT=500"
	@echo "  make logs-f agents"
	@echo "  make db-backup"
	@echo ""

# ─────────────────────────────────────────────────────────────────────────────
# STACK MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
up: check-env ## Start full dev stack (hot reload, all services)
	@./scripts/start.sh dev
	@echo ""

dev: up ## Alias for 'make up'

prod: check-env ## Start production stack (Traefik TLS, replicas)
	@./scripts/start.sh prod

down: ## Stop all services (preserves volumes)
	$(COMPOSE_DEV) down

down-prod: ## Stop production stack
	$(COMPOSE_PROD) down

down-all: ## Stop all services AND remove volumes (data loss!)
	@echo "\033[1;31mThis will DELETE all data. Are you sure? [y/N]\033[0m" && read ans && [ $${ans:-N} = y ]
	$(COMPOSE_DEV) down -v --remove-orphans

restart: ## Restart all services
	$(COMPOSE_DEV) restart

restart-%: ## Restart specific service: make restart-platform
	$(COMPOSE_DEV) restart $*

build: ## Rebuild all Docker images (no cache)
	$(COMPOSE_DEV) build --no-cache --parallel

build-%: ## Rebuild specific service: make build-platform
	$(COMPOSE_DEV) build --no-cache $*

pull: ## Pull latest base images
	$(COMPOSE_DEV) pull

# ─────────────────────────────────────────────────────────────────────────────
# MONITORING
# ─────────────────────────────────────────────────────────────────────────────
status: ## Show status of all containers
	$(COMPOSE_DEV) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

health: ## Run full stack health check
	@./scripts/healthcheck.sh

logs: ## Follow logs from all services
	$(COMPOSE_DEV) logs -f --tail=100

logs-f: ## Follow logs from specific service: make logs-f agents
	$(COMPOSE_DEV) logs -f --tail=200 $(filter-out $@,$(MAKECMDGOALS))

%:  # Catch-all to support `make logs-f platform` style
	@:

stats: ## Show container resource usage
	docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# ─────────────────────────────────────────────────────────────────────────────
# SHELLS
# ─────────────────────────────────────────────────────────────────────────────
shell-platform: ## Open shell in Next.js container
	$(COMPOSE_DEV) exec platform sh

shell-agents: ## Open shell in FastAPI container
	$(COMPOSE_DEV) exec agents bash

shell-worker: ## Open shell in Celery worker container
	$(COMPOSE_DEV) exec worker bash

shell-db: ## Open PostgreSQL psql shell
	$(COMPOSE_DEV) exec postgres psql -U $${POSTGRES_USER:-aiwebgen} $${POSTGRES_DB:-ai_web_gen}

shell-redis: ## Open Redis CLI
	$(COMPOSE_DEV) exec redis redis-cli

# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────
crawl: ## Discover businesses: make crawl CITY=Warsaw CATEGORY=restaurant
	@echo "\033[1;34m▶ Crawling: $(CITY) / $(CATEGORY) (limit: $(LIMIT))\033[0m"
	$(COMPOSE_DEV) run --rm \
		-e CRAWL_CITY="$(CITY)" \
		-e CRAWL_CATEGORY="$(CATEGORY)" \
		-e CRAWL_SOURCE="$(SOURCE)" \
		-e CRAWL_LIMIT="$(LIMIT)" \
		crawler

crawl-all: ## Run crawler for all major Polish cities + top categories
	@echo "\033[1;34m▶ Running comprehensive Poland crawl...\033[0m"
	@for city in Warsaw Kraków Wrocław Gdańsk Poznań Łódź; do \
		for cat in restaurant beauty_salon dental_clinic plumber; do \
			$(MAKE) crawl CITY="$$city" CATEGORY="$$cat" LIMIT=200; \
		done; \
	done

process-leads: ## Trigger AI pipeline for all unprocessed leads
	@echo "\033[1;34m▶ Processing pending leads via Celery...\033[0m"
	$(COMPOSE_DEV) exec worker \
		celery -A tasks call tasks.process_pending_leads --kwargs='{"limit":100}'

send-campaign: ## Send campaign batch: make send-campaign CAMPAIGN_ID=xxx
	$(COMPOSE_DEV) exec worker \
		celery -A tasks call tasks.send_campaign_batch --kwargs='{"campaign_id":"$(CAMPAIGN_ID)","batch_size":20}'

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────
db-migrate: ## Apply Prisma schema to database
	$(COMPOSE_DEV) exec platform npx prisma db push

db-migrate-prod: ## Run production migration (safe)
	$(COMPOSE_DEV) exec platform npx prisma migrate deploy

db-seed: ## Seed database with demo data
	$(COMPOSE_DEV) exec platform npx prisma db seed

db-reset: ## Drop and recreate database (DEV ONLY — data loss!)
	@echo "\033[1;31mThis will DELETE all data! [y/N]\033[0m" && read ans && [ $${ans:-N} = y ]
	$(COMPOSE_DEV) exec platform npx prisma db push --force-reset
	$(MAKE) db-seed

db-studio: ## Open Prisma Studio (visual DB editor)
	$(COMPOSE_DEV) exec platform npx prisma studio --port 5555

db-backup: ## Create database backup
	@./scripts/backup.sh

db-restore: ## Restore database: make db-restore FILE=backups/aiwebgen_xxx.sql.gz
	@[ -f "$(FILE)" ] || (echo "FILE not specified. Usage: make db-restore FILE=backups/aiwebgen_xxx.sql.gz" && exit 1)
	gunzip -c $(FILE) | docker exec -i aiwebgen-postgres psql \
		-U $${POSTGRES_USER:-aiwebgen} $${POSTGRES_DB:-ai_web_gen}

# ─────────────────────────────────────────────────────────────────────────────
# CELERY MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
celery-status: ## Show Celery worker status
	$(COMPOSE_DEV) exec worker celery -A tasks inspect active

celery-purge: ## Purge all pending tasks (careful!)
	$(COMPOSE_DEV) exec worker celery -A tasks purge -f

celery-scale: ## Scale workers: make celery-scale N=3
	$(COMPOSE_DEV) scale worker=$(N)

# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────
clean: ## Remove stopped containers and unused images
	docker container prune -f
	docker image prune -f

clean-all: ## Full cleanup (containers, images, networks — NOT volumes)
	$(COMPOSE_DEV) down --remove-orphans
	docker system prune -f

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
check-env: ## Verify required environment setup
	@[ -f .env ] || (cp .env.example .env && echo "\033[1;33m.env created from .env.example — fill in your API keys!\033[0m")
	@command -v docker >/dev/null 2>&1 || (echo "\033[1;31mDocker not found!\033[0m" && exit 1)
	@docker info >/dev/null 2>&1 || (echo "\033[1;31mDocker daemon not running!\033[0m" && exit 1)

setup: ## First-time setup: copy .env, create directories
	@cp -n .env.example .env 2>/dev/null || true
	@mkdir -p backups crawler/data agents/logs platform/logs
	@echo "\033[1;32m✓ Setup complete. Edit .env with your API keys, then run: make up\033[0m"
