"""
FastAPI server that exposes the agent pipeline as an HTTP API.
Called by the Next.js platform when generating demo sites for leads.

Run:
    uvicorn api_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import hmac
import os
import warnings
from typing import Optional

import structlog
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator

from config import settings
from pipeline import process_business
from models import ProcessedBusiness

log = structlog.get_logger()

app = FastAPI(
    title="AI Web Generator — Agent API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
)

_default_origins = (
    "https://yourplatform.pl,http://localhost:3000"
    if os.getenv("ENV") == "production"
    else "https://yourplatform.pl,http://localhost:3000,http://localhost"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", _default_origins).split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["X-Api-Secret", "Content-Type"],
)

# Prometheus instrumentation (adds /metrics endpoint)
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False, tags=["observability"])
except ImportError:
    pass  # optional — works without prometheus_fastapi_instrumentator

# Redis-backed job tracking for multi-instance support
import json as _json

_redis_client = None


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
        )
    return _redis_client


async def _store_job(job_id: str, data: dict, ttl: int = 86400):
    """Store job data in Redis with TTL (default 24h)."""
    try:
        r = await _get_redis()
        await r.setex(f"job:{job_id}", ttl, _json.dumps(data, default=str))
    except Exception:
        log.warning("redis.store_job.failed", job_id=job_id)


async def _get_job(job_id: str) -> dict | None:
    """Retrieve job data from Redis."""
    try:
        r = await _get_redis()
        raw = await r.get(f"job:{job_id}")
        return _json.loads(raw) if raw else None
    except Exception:
        return None


class ProcessRequest(BaseModel):
    place_id: str
    name: str
    address: str
    city: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    category: str = "other"
    rating: Optional[float] = None
    review_count: Optional[int] = None


class ProcessResponse(BaseModel):
    success: bool
    demo_site_url: Optional[str] = None
    demo_site_slug: Optional[str] = None
    design_spec: Optional[dict] = None
    content: Optional[dict] = None
    qc_result: Optional[dict] = None
    pipeline_duration_s: Optional[float] = None
    error: Optional[str] = None


async def verify_api_secret(x_api_secret: Optional[str] = Header(None)) -> None:
    """FastAPI dependency: timing-safe API secret verification."""
    expected = os.getenv("AGENT_API_SECRET")
    if not expected:
        warnings.warn("AGENT_API_SECRET not set — API endpoints are unauthenticated", stacklevel=2)
        return
    if not x_api_secret or not hmac.compare_digest(x_api_secret.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health", include_in_schema=False)
async def health():
    """Health check — used by Docker + Nginx."""
    import redis.asyncio as aioredis
    redis_ok = False
    r = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        pass
    finally:
        await r.aclose()

    status = "healthy" if redis_ok else "degraded"
    return {"status": status, "version": "1.0.0", "redis": redis_ok}


@app.post("/process", response_model=ProcessResponse, dependencies=[Depends(verify_api_secret)])
async def process(request: ProcessRequest):
    """Synchronously process a single business through the full 6-agent pipeline."""

    try:
        result = await process_business(request.model_dump())
        if result is None:
            return ProcessResponse(success=False, error="Business skipped (good website or duplicate)")

        return ProcessResponse(
            success=True,
            demo_site_url=result.demo_site_url,
            demo_site_slug=result.demo_site_slug,
            design_spec=result.design_spec.model_dump() if result.design_spec else None,
            content=result.content.model_dump() if result.content else None,
            qc_result=result.qc_result.model_dump() if result.qc_result else None,
            pipeline_duration_s=result.pipeline_duration_s,
        )
    except Exception as exc:
        log.error("pipeline.error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error") from exc


class BatchRequest(BaseModel):
    businesses: list[ProcessRequest]
    concurrency: int = 5

    @field_validator("businesses")
    @classmethod
    def limit_batch_size(cls, v):
        if len(v) > 500:
            raise ValueError("Maximum 500 businesses per batch")
        return v

    @field_validator("concurrency")
    @classmethod
    def clamp_concurrency(cls, v):
        return max(1, min(v, 20))


class BatchJobResponse(BaseModel):
    job_id: str
    total: int
    status: str = "queued"


@app.post("/process/batch", response_model=BatchJobResponse, dependencies=[Depends(verify_api_secret)])
async def process_batch_async(
    request: BatchRequest,
    background_tasks: BackgroundTasks,
):
    """Queue a batch of businesses for async processing."""

    import uuid
    job_id = str(uuid.uuid4())
    job_data = {"status": "running", "total": len(request.businesses), "completed": 0, "results": []}
    await _store_job(job_id, job_data)

    async def run_batch():
        from pipeline import process_batch
        results = await process_batch(
            [b.model_dump() for b in request.businesses],
            request.concurrency,
        )
        await _store_job(job_id, {
            "status": "completed",
            "total": len(request.businesses),
            "completed": len(results),
            "results": [r.model_dump(mode="json") for r in results],
        })

    background_tasks.add_task(run_batch)

    return BatchJobResponse(job_id=job_id, total=len(request.businesses))


@app.get("/jobs/{job_id}", dependencies=[Depends(verify_api_secret)])
async def get_job_status(job_id: str):
    job = await _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
