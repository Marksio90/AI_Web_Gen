# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder — install dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runner — production image (~400 MB)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN groupadd -g 1001 python && \
    useradd -u 1001 -g python -m -s /bin/bash python

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=python:python . .

USER python

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
