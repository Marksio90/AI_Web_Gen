################################################################################
# ⚡ AI Local Business Website Generator — Master Makefile
################################################################################
.DEFAULT_GOAL := help
.PHONY: help up dev prod down restart build pull logs logs-f status health \
        shell-platform shell-agents shell-worker shell-db shell-redis \
        crawl crawl-all process-leads send-campaign \
        db-migrate db-seed db-reset db-studio db-backup db-restore \
        celery-status celery-purge celery-scale \
        monitoring-up monitoring-down \
        clean clean-all setup check-env

# ─── Variables ────────────────────────────────────────────────────────────────
COMPOSE     := docker compose
DEV_FLAGS   := -f docker-compose.yml -f docker-compose.dev.yml
PROD_FLAGS  := -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_DEV := $(COMPOSE) $(DEV_FLAGS)
COMPOSE_PROD:= $(COMPOSE) $(PROD_FLAGS)

CITY          ?= Warsaw
CATEGORY      ?= restaurant
SOURCE        ?= both
LIMIT         ?= 200
CAMPAIGN_ID   ?=
N             ?= 2

# Colors & symbols
RESET  := \033[0m
BOLD   := \033[1m
DIM    := \033[2m
RED    := \033[31m
GREEN  := \033[32m
YELLOW := \033[33m
BLUE   := \033[34m
CYAN   := \033[36m
WHITE  := \033[97m

define HEADER
	@printf "\n$(BLUE)$(BOLD)╔══════════════════════════════════════════════════════════╗$(RESET)\n"
	@printf "$(BLUE)$(BOLD)║  ⚡ AI Web Generator  %-37s║$(RESET)\n" "$1"
	@printf "$(BLUE)$(BOLD)╚══════════════════════════════════════════════════════════╝$(RESET)\n\n"
endef

# ─────────────────────────────────────────────────────────────────────────────
# HELP — generated from ## comments
# ─────────────────────────────────────────────────────────────────────────────
help:
	$(call HEADER,Available Commands)
	@printf "$(BOLD)$(WHITE)  STACK$(RESET)\n"
	@awk 'BEGIN{FS=":.*##"} \
	  /^##/{printf "\n$(DIM)  %s$(RESET)\n",substr($$0,3)} \
	  /^[a-zA-Z0-9_-]+:.*##/{printf "  $(CYAN)%-22s$(RESET) %s\n",$$1,$$2}' \
	  $(MAKEFILE_LIST)
	@printf "\n$(BOLD)$(WHITE)  QUICK EXAMPLES$(RESET)\n"
	@printf "  $(DIM)make crawl CITY=Kraków CATEGORY=beauty_salon LIMIT=500$(RESET)\n"
	@printf "  $(DIM)make logs-f agents$(RESET)\n"
	@printf "  $(DIM)make db-backup$(RESET)\n"
	@printf "  $(DIM)make scale-worker N=4$(RESET)\n"
	@printf "\n"

## Stack management
up: check-env ## 🚀 Start full dev stack (hot reload, all 10 services)
	$(call HEADER,Starting DEV Stack)
	@./scripts/start.sh dev

dev: up ## Alias for 'make up'

prod: check-env ## 🏭 Start production stack (Traefik TLS, replicas, no hot reload)
	$(call HEADER,Starting PROD Stack)
	@./scripts/start.sh prod

down: ## ⏹  Stop all services (data preserved)
	@printf "$(YELLOW)Stopping all services...$(RESET)\n"
	@$(COMPOSE_DEV) down --remove-orphans
	@printf "$(GREEN)✓ All services stopped$(RESET)\n"

down-clean: ## 💣 Stop all services + delete ALL volumes (data loss!)
	@printf "$(RED)$(BOLD)⚠ This will DELETE all database data!$(RESET)\n"
	@read -p "Type 'yes' to confirm: " c && [ "$$c" = "yes" ] || exit 1
	@$(COMPOSE_DEV) down -v --remove-orphans
	@printf "$(GREEN)✓ Clean shutdown complete$(RESET)\n"

restart: ## 🔄 Restart all services
	@$(COMPOSE_DEV) restart

restart-%: ## 🔄 Restart specific service: make restart-platform
	@$(COMPOSE_DEV) restart $*
	@printf "$(GREEN)✓ $* restarted$(RESET)\n"

## Build
build: check-env ## 🔨 Rebuild all images (parallel, no cache)
	$(call HEADER,Building All Images)
	@$(COMPOSE_DEV) build --no-cache --parallel
	@printf "\n$(GREEN)$(BOLD)✓ All images built$(RESET)\n"

build-%: ## 🔨 Rebuild specific service image: make build-platform
	@$(COMPOSE_DEV) build --no-cache $*

pull: ## ⬇  Pull latest base images
	@$(COMPOSE_DEV) pull

## Monitoring & status
status: ## 📊 Show status of all containers (name/health/ports)
	@$(COMPOSE_DEV) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

health: ## 🏥 Run full stack health check (HTTP + Docker + TCP)
	$(call HEADER,Health Check)
	@./scripts/healthcheck.sh

logs: ## 📜 Follow logs from ALL services (last 100 lines)
	@$(COMPOSE_DEV) logs -f --tail=100

logs-f: ## 📜 Follow logs from a specific service: make logs-f platform
	@$(COMPOSE_DEV) logs -f --tail=200 $(filter-out $@,$(MAKECMDGOALS))

stats: ## 📈 Live container resource usage (CPU/memory/network)
	@docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

## Shells
shell-platform: ## 💻 Open shell inside Next.js container
	@$(COMPOSE_DEV) exec platform sh

shell-agents: ## 🐍 Open shell inside FastAPI/agents container
	@$(COMPOSE_DEV) exec agents bash

shell-worker: ## 🐍 Open shell inside Celery worker container
	@$(COMPOSE_DEV) exec worker bash

shell-db: ## 🗄  Open PostgreSQL psql interactive shell
	@$(COMPOSE_DEV) exec postgres psql -U $${POSTGRES_USER:-aiwebgen} $${POSTGRES_DB:-ai_web_gen}

shell-redis: ## 🔴 Open Redis CLI interactive shell
	@$(COMPOSE_DEV) exec redis redis-cli

## Business Discovery
crawl: ## 🔍 Discover businesses: make crawl CITY=Warsaw CATEGORY=restaurant LIMIT=200
	$(call HEADER,Crawling $CITY / $CATEGORY)
	@printf "$(CYAN)City:$(RESET)     $(CITY)\n"
	@printf "$(CYAN)Category:$(RESET) $(CATEGORY)\n"
	@printf "$(CYAN)Limit:$(RESET)    $(LIMIT)\n\n"
	@$(COMPOSE_DEV) run --rm \
		-e CRAWL_CITY="$(CITY)" \
		-e CRAWL_CATEGORY="$(CATEGORY)" \
		-e CRAWL_SOURCE="$(SOURCE)" \
		-e CRAWL_LIMIT="$(LIMIT)" \
		crawler
	@printf "\n$(GREEN)✓ Crawl complete$(RESET)\n"

crawl-all: ## 🌍 Crawl all major Polish cities × top 4 categories
	$(call HEADER,Full Poland Sweep)
	@for city in Warsaw Kraków Wrocław Gdańsk Poznań Łódź Katowice Szczecin; do \
		for cat in restaurant beauty_salon dental_clinic plumber; do \
			printf "$(CYAN)▶ $$city / $$cat$(RESET)\n"; \
			$(MAKE) -s crawl CITY="$$city" CATEGORY="$$cat" LIMIT=200; \
		done; \
	done
	@printf "\n$(GREEN)$(BOLD)✓ Full Poland sweep complete!$(RESET)\n"

process-leads: ## ⚙️  Trigger AI pipeline for all DISCOVERED leads (via Celery)
	@printf "$(CYAN)Queuing pipeline for pending leads...$(RESET)\n"
	@$(COMPOSE_DEV) exec worker \
		celery -A tasks call tasks.process_pending_leads --kwargs='{"limit":100}'
	@printf "$(GREEN)✓ Tasks queued — check Flower for progress$(RESET)\n"

send-campaign: ## 📧 Send campaign batch: make send-campaign CAMPAIGN_ID=cuid
	@[ -n "$(CAMPAIGN_ID)" ] || (printf "$(RED)CAMPAIGN_ID required$(RESET)\n" && exit 1)
	@$(COMPOSE_DEV) exec worker \
		celery -A tasks call tasks.send_campaign_batch \
		--kwargs='{"campaign_id":"$(CAMPAIGN_ID)","batch_size":20}'

## Database
db-migrate: ## 🗄  Apply Prisma schema changes to database
	@printf "$(CYAN)Running database migration...$(RESET)\n"
	@$(COMPOSE_DEV) exec platform npx prisma db push
	@printf "$(GREEN)✓ Schema applied$(RESET)\n"

db-seed: ## 🌱 Seed database with demo leads and data
	@$(COMPOSE_DEV) exec platform npx prisma db seed
	@printf "$(GREEN)✓ Database seeded$(RESET)\n"

db-reset: ## 💣 Drop + recreate DB + re-seed (DEV ONLY — data loss!)
	@printf "$(RED)$(BOLD)⚠ This will DELETE all database data!$(RESET)\n"
	@read -p "Type 'yes' to confirm: " c && [ "$$c" = "yes" ] || exit 1
	@$(COMPOSE_DEV) exec platform npx prisma db push --force-reset
	@$(MAKE) db-seed
	@printf "$(GREEN)✓ Database reset and seeded$(RESET)\n"

db-studio: ## 🎨 Open Prisma Studio (visual DB browser) at :5555
	@printf "$(CYAN)Starting Prisma Studio at http://localhost:5555$(RESET)\n"
	@$(COMPOSE_DEV) exec platform npx prisma studio --port 5555

db-backup: ## 💾 Create timestamped DB backup in ./backups/
	$(call HEADER,Database Backup)
	@./scripts/backup.sh

db-restore: ## 💾 Restore DB backup: make db-restore FILE=backups/aiwebgen_xxx.sql.gz
	@[ -f "$(FILE)" ] || (printf "$(RED)FILE required: make db-restore FILE=path/to/backup.sql.gz$(RESET)\n" && exit 1)
	@printf "$(YELLOW)Restoring from $(FILE)...$(RESET)\n"
	@gunzip -c $(FILE) | docker exec -i aiwebgen-postgres psql \
		-U $${POSTGRES_USER:-aiwebgen} $${POSTGRES_DB:-ai_web_gen}
	@printf "$(GREEN)✓ Restore complete$(RESET)\n"

## Celery
celery-status: ## 🌸 Show active Celery tasks across all workers
	@$(COMPOSE_DEV) exec worker celery -A tasks inspect active --timeout 10

celery-queues: ## 🌸 Show Celery queue lengths
	@$(COMPOSE_DEV) exec worker celery -A tasks inspect reserved --timeout 10

celery-purge: ## 🗑  Purge ALL pending Celery tasks (careful!)
	@printf "$(RED)Purging all tasks...$(RESET)\n"
	@$(COMPOSE_DEV) exec worker celery -A tasks purge -f
	@printf "$(GREEN)✓ All tasks purged$(RESET)\n"

scale-worker: ## ⚡ Scale Celery workers: make scale-worker N=3
	@$(COMPOSE_DEV) up -d --scale worker=$(N) worker
	@printf "$(GREEN)✓ Scaled to $(N) worker instance(s)$(RESET)\n"

## Monitoring
monitoring-open: ## 📊 Open all monitoring dashboards in browser
	@command -v xdg-open >/dev/null && OPEN=xdg-open || OPEN=open; \
	$$OPEN http://localhost:3001 2>/dev/null; \
	$$OPEN http://localhost:9090 2>/dev/null; \
	$$OPEN http://localhost:5556 2>/dev/null

## Cleanup
clean: ## 🧹 Remove stopped containers + dangling images
	@docker container prune -f
	@docker image prune -f
	@printf "$(GREEN)✓ Cleaned stopped containers and dangling images$(RESET)\n"

clean-all: ## 🧹 Full Docker cleanup (containers, images, networks — NOT volumes)
	@$(COMPOSE_DEV) down --remove-orphans
	@docker system prune -af --volumes=false
	@printf "$(GREEN)✓ Full cleanup complete$(RESET)\n"

## Setup helpers
setup: ## 🛠  First-time setup: copy .env, create directories
	$(call HEADER,First-Time Setup)
	@cp -n .env.example .env 2>/dev/null && \
		printf "$(YELLOW)✓ .env created — fill in your API keys!$(RESET)\n" || \
		printf "$(DIM).env already exists$(RESET)\n"
	@mkdir -p backups crawler/data agents/logs
	@chmod +x scripts/*.sh 2>/dev/null || true
	@printf "$(GREEN)$(BOLD)✓ Setup complete!$(RESET)\n"
	@printf "\nNext step: $(CYAN)nano .env$(RESET) → fill in OPENAI_API_KEY etc.\n"
	@printf "Then run:   $(CYAN)make up$(RESET)\n\n"

check-env: ## ✅ Verify Docker + .env prerequisites
	@[ -f .env ] || (cp .env.example .env && printf "$(YELLOW)⚠ Created .env from template — fill in API keys!$(RESET)\n")
	@command -v docker >/dev/null 2>&1 || (printf "$(RED)✗ Docker not found$(RESET)\n" && exit 1)
	@docker info >/dev/null 2>&1 || (printf "$(RED)✗ Docker daemon not running$(RESET)\n" && exit 1)
	@docker compose version >/dev/null 2>&1 || (printf "$(RED)✗ Docker Compose v2 required$(RESET)\n" && exit 1)

# Catch-all to allow `make logs-f platform` without error
%:
	@true
