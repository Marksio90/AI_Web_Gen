#!/usr/bin/env bash
################################################################################
# start.sh — Smart startup script
# Called by `make up` — detects if .env exists, checks Docker, starts stack
################################################################################
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

COMPOSE_BASE="docker compose"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

header() { echo -e "\n${BLUE}${BOLD}▶ $*${NC}"; }
ok()     { echo -e "${GREEN}✓ $*${NC}"; }
warn()   { echo -e "${YELLOW}⚠ $*${NC}"; }
fail()   { echo -e "${RED}✗ $*${NC}"; exit 1; }

# ─── Check prerequisites ──────────────────────────────────────────────────────
header "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || fail "Docker not found. Install from https://docker.com"
docker info >/dev/null 2>&1 || fail "Docker daemon not running. Start Docker Desktop or 'sudo systemctl start docker'"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 not found. Update Docker."

ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
ok "Docker Compose $(docker compose version --short)"

# ─── Check .env ───────────────────────────────────────────────────────────────
header "Checking environment..."

if [ ! -f "$ROOT/.env" ]; then
  warn ".env file not found. Copying from .env.example..."
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo -e "\n${YELLOW}${BOLD}ACTION REQUIRED:${NC}"
  echo "Edit .env and fill in your API keys before proceeding:"
  echo "  - OPENAI_API_KEY (required)"
  echo "  - POSTGRES_PASSWORD (change from default)"
  echo "  - AUTH_SECRET (generate: openssl rand -base64 32)"
  echo ""
  read -p "Press Enter to continue with current settings (dev mode) or Ctrl+C to edit .env first..."
fi

source "$ROOT/.env" 2>/dev/null || true

[ -z "${OPENAI_API_KEY:-}" ] && warn "OPENAI_API_KEY not set — agent pipeline will fail"
[ -z "${AUTH_SECRET:-}" ]    && warn "AUTH_SECRET not set — using insecure default"
ok ".env loaded"

# ─── Mode selection ───────────────────────────────────────────────────────────
MODE="${1:-dev}"

if [ "$MODE" = "prod" ]; then
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
  ok "Mode: PRODUCTION (Traefik TLS)"
else
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
  ok "Mode: DEVELOPMENT (hot reload)"
fi

# ─── Build images ─────────────────────────────────────────────────────────────
header "Building Docker images..."
docker compose $COMPOSE_FILES build --parallel

# ─── Start services ───────────────────────────────────────────────────────────
header "Starting services..."
docker compose $COMPOSE_FILES up -d --remove-orphans

# ─── Wait for health ──────────────────────────────────────────────────────────
header "Waiting for services to be healthy..."

wait_healthy() {
  local service="$1"
  local max_wait="${2:-120}"
  local elapsed=0
  echo -n "  Waiting for $service..."
  while [ $elapsed -lt $max_wait ]; do
    STATUS=$(docker compose $COMPOSE_FILES ps --format json "$service" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "")
    if [ "$STATUS" = "healthy" ]; then
      echo -e " ${GREEN}healthy${NC}"
      return 0
    fi
    echo -n "."
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo -e " ${YELLOW}timeout (continuing anyway)${NC}"
}

wait_healthy postgres 60
wait_healthy redis 30
wait_healthy platform 120
wait_healthy agents 60

# ─── Final status ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║           AI Web Generator — Stack Running!              ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Platform (Next.js):${NC}    http://localhost"
echo -e "  ${BOLD}Agent API (FastAPI):${NC}   http://localhost:8001/docs"
echo -e "  ${BOLD}Celery Monitor:${NC}        http://localhost:5556"
echo -e "  ${BOLD}DB Admin (Adminer):${NC}    http://localhost:8082"

if [ "$MODE" = "dev" ]; then
  echo -e "  ${BOLD}Redis Commander:${NC}       http://localhost:8083"
  echo -e "  ${BOLD}Email Catcher:${NC}         http://localhost:8025"
fi

echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "  make logs       — follow all logs"
echo -e "  make logs-f X  — follow service X logs"
echo -e "  make crawl      — run business discovery"
echo -e "  make shell-platform  — Next.js shell"
echo -e "  make shell-agents    — Python agent shell"
echo -e "  make down       — stop everything"
echo ""
