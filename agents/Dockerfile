# ─────────────────────────────────────────────────────────────────────────────
# AI Web Generator — Agents + Crawler (unified image)
#
# IMPORTANT: build context = repo ROOT (set in docker-compose.yml)
# This allows copying both agents/ AND crawler/ into one image.
# ─────────────────────────────────────────────────────────────────────────────

# Stage 1: builder — fast dependency install with uv
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN pip install --no-cache-dir uv

COPY agents/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runner — minimal production image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1001 appuser && \
    useradd -u 1001 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy agents (main app) + crawler (imported by tasks.py)
COPY --chown=appuser:appuser agents/ /app/
COPY --chown=appuser:appuser crawler/ /app/crawler/

USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8000/health | python3 -c \
    "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='healthy' else 1)"

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--access-log"]
