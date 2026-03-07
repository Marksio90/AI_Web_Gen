#!/usr/bin/env bash
# Full stack health check — run after `make up`
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'; BOLD='\033[1m'

pass() { echo -e "  ${GREEN}✓${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; FAILED=$((FAILED+1)); }
skip() { echo -e "  ${YELLOW}−${NC} $*"; }

FAILED=0

check_http() {
  local name="$1" url="$2" expected="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "$expected" ] || [ "$code" = "200" ] || [ "$code" = "307" ] || [ "$code" = "302" ]; then
    pass "$name ($url) → HTTP $code"
  else
    fail "$name ($url) → HTTP $code (expected $expected)"
  fi
}

check_tcp() {
  local name="$1" host="$2" port="$3"
  if timeout 3 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
    pass "$name ($host:$port) → TCP open"
  else
    fail "$name ($host:$port) → TCP closed/timeout"
  fi
}

check_docker() {
  local name="$1"
  local status
  status=$(docker inspect --format='{{.State.Health.Status}}' "aiwebgen-$name" 2>/dev/null || echo "not found")
  if [ "$status" = "healthy" ]; then
    pass "$name → $status"
  elif [ "$status" = "not found" ]; then
    fail "$name → container not found"
  else
    fail "$name → $status"
  fi
}

echo ""
echo -e "${BOLD}━━━ Docker Container Health ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_docker postgres
check_docker redis
check_docker platform
check_docker agents
check_docker worker
check_docker flower

echo ""
echo -e "${BOLD}━━━ HTTP Endpoints ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_http "Platform homepage"    "http://localhost"
check_http "Platform health API"  "http://localhost/api/health"
check_http "Agent API health"     "http://localhost:8001/health"
check_http "Agent API docs"       "http://localhost:8001/docs"
check_http "Flower UI"            "http://localhost:5556"
check_http "Adminer"              "http://localhost:8082"
check_http "Prometheus"           "http://localhost:9090/-/ready"
check_http "Grafana"              "http://localhost:3001/api/health"

echo ""
echo -e "${BOLD}━━━ TCP Connectivity ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_tcp "PostgreSQL" localhost 5432
check_tcp "Redis"      localhost 6379

echo ""
if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}${BOLD}All checks passed! Stack is fully operational.${NC}"
else
  echo -e "${RED}${BOLD}$FAILED check(s) failed. Run 'make logs' to investigate.${NC}"
  exit 1
fi
echo ""
