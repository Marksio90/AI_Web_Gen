"""
Advanced FastAPI server for the Multi-Agent Platform.

Features:
- Standard REST API for pipeline execution
- Server-Sent Events (SSE) for real-time pipeline streaming
- Strategy selection endpoint
- Agent memory & performance analytics
- Swarm decision history
- Pipeline telemetry dashboard
- Health checks with component status

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
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, field_validator

from config import settings
from events import EventCategory, get_event_bus
from memory import get_memory_store
from models import PipelineStrategy, ProcessedBusiness

log = structlog.get_logger()

app = FastAPI(
    title="AI Web Generator — Advanced Multi-Agent Platform",
    version="2.0.0",
    description=(
        "Futuristic multi-agent pipeline with DAG orchestration, "
        "swarm intelligence, evolutionary optimization, and real-time telemetry."
    ),
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

# Prometheus instrumentation
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, include_in_schema=False, tags=["observability"])
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Redis job store
# ---------------------------------------------------------------------------
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
    try:
        r = await _get_redis()
        await r.setex(f"job:{job_id}", ttl, _json.dumps(data, default=str))
    except Exception:
        log.warning("redis.store_job.failed", job_id=job_id)


async def _get_job(job_id: str) -> dict | None:
    try:
        r = await _get_redis()
        raw = await r.get(f"job:{job_id}")
        return _json.loads(raw) if raw else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def verify_api_secret(x_api_secret: Optional[str] = Header(None)) -> None:
    expected = os.getenv("AGENT_API_SECRET")
    if not expected:
        warnings.warn("AGENT_API_SECRET not set — API endpoints are unauthenticated", stacklevel=2)
        return
    if not x_api_secret or not hmac.compare_digest(x_api_secret.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

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
    strategy: Optional[str] = None  # auto, standard, swarm, evolutionary, turbo, premium


class ProcessResponse(BaseModel):
    success: bool
    demo_site_url: Optional[str] = None
    demo_site_slug: Optional[str] = None
    design_spec: Optional[dict] = None
    content: Optional[dict] = None
    qc_result: Optional[dict] = None
    competitive_intel: Optional[dict] = None
    pipeline_duration_s: Optional[float] = None
    strategy_used: Optional[str] = None
    quality_confidence: Optional[float] = None
    telemetry: Optional[dict] = None
    error: Optional[str] = None


class BatchRequest(BaseModel):
    businesses: list[ProcessRequest]
    concurrency: int = 5
    strategy: Optional[str] = None

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
    strategy: Optional[str] = None


# ---------------------------------------------------------------------------
# Health & System
# ---------------------------------------------------------------------------

@app.get("/health", include_in_schema=False)
async def health():
    """Health check with component status."""
    import redis.asyncio as aioredis
    components = {"redis": False, "memory": False, "events": False}

    # Redis
    try:
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        await r.ping()
        components["redis"] = True
        await r.aclose()
    except Exception:
        pass

    # Memory store
    try:
        memory = get_memory_store()
        await memory.initialize()
        components["memory"] = True
    except Exception:
        pass

    # Event bus
    try:
        event_bus = get_event_bus()
        components["events"] = True
    except Exception:
        pass

    all_healthy = all(components.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "2.0.0",
        "platform": "multi-agent-v2",
        "components": components,
        "features": {
            "swarm_intelligence": settings.enable_swarm,
            "evolutionary_optimization": settings.enable_evolution,
            "agent_memory": settings.enable_memory,
            "event_streaming": settings.enable_events,
            "dynamic_routing": settings.enable_dynamic_routing,
            "auto_strategy": settings.auto_select_strategy,
        },
    }


@app.get("/system/capabilities", tags=["system"])
async def system_capabilities():
    """Return platform capabilities and available strategies."""
    return {
        "strategies": [
            {
                "id": s.value,
                "description": {
                    "standard": "Linear 6-agent pipeline — balanced quality and speed",
                    "swarm": "Multi-agent voting on design & content — best for ambiguous cases",
                    "evolutionary": "Genetic algorithm for content optimization — best quality",
                    "turbo": "Parallel fast-path — maximum speed",
                    "premium": "All engines combined — maximum quality for high-value leads",
                    "debate": "Adversarial debate protocol — best for edge cases",
                }[s.value],
            }
            for s in PipelineStrategy
            if s.value != "debate"  # debate uses swarm internally
        ],
        "agents": {
            "core": ["crawler", "seo", "design", "content", "email", "qc"],
            "meta": ["orchestrator", "competitive_intel", "content_refinement",
                     "design_critic", "seo_optimizer", "personalization"],
        },
        "engines": [
            "dag_orchestrator",
            "swarm_intelligence",
            "evolutionary_optimizer",
            "multi_model_router",
            "ensemble_scorer",
            "chain_of_thought",
            "agent_memory",
            "event_bus",
        ],
    }


# ---------------------------------------------------------------------------
# Pipeline Endpoints
# ---------------------------------------------------------------------------

@app.post("/process", response_model=ProcessResponse, dependencies=[Depends(verify_api_secret)],
          tags=["pipeline"])
async def process(request: ProcessRequest):
    """Process a single business through the multi-agent pipeline."""
    from pipeline import process_business

    try:
        result = await process_business(
            request.model_dump(exclude={"strategy"}),
            strategy=request.strategy,
        )
        if result is None:
            return ProcessResponse(success=False, error="Business skipped (good website or duplicate)")

        return ProcessResponse(
            success=True,
            demo_site_url=result.demo_site_url,
            demo_site_slug=result.demo_site_slug,
            design_spec=result.design_spec.model_dump() if result.design_spec else None,
            content=result.content.model_dump() if result.content else None,
            qc_result=result.qc_result.model_dump() if result.qc_result else None,
            competitive_intel=result.competitive_intel.model_dump() if result.competitive_intel else None,
            pipeline_duration_s=result.pipeline_duration_s,
            strategy_used=result.strategy_used.value if result.strategy_used else None,
            quality_confidence=result.quality_confidence,
            telemetry=result.telemetry.model_dump() if result.telemetry else None,
        )
    except Exception as exc:
        log.error("pipeline.error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error") from exc


@app.post("/process/batch", response_model=BatchJobResponse, dependencies=[Depends(verify_api_secret)],
          tags=["pipeline"])
async def process_batch_async(request: BatchRequest, background_tasks: BackgroundTasks):
    """Queue a batch of businesses for async processing."""
    import uuid
    job_id = str(uuid.uuid4())
    job_data = {
        "status": "running",
        "total": len(request.businesses),
        "completed": 0,
        "results": [],
        "strategy": request.strategy or "auto",
    }
    await _store_job(job_id, job_data)

    async def run_batch():
        from pipeline import process_batch
        results = await process_batch(
            [b.model_dump(exclude={"strategy"}) for b in request.businesses],
            request.concurrency,
            strategy=request.strategy,
        )
        await _store_job(job_id, {
            "status": "completed",
            "total": len(request.businesses),
            "completed": len(results),
            "results": [r.model_dump(mode="json") for r in results],
            "strategy": request.strategy or "auto",
        })

    background_tasks.add_task(run_batch)
    return BatchJobResponse(
        job_id=job_id,
        total=len(request.businesses),
        strategy=request.strategy or "auto",
    )


@app.get("/jobs/{job_id}", dependencies=[Depends(verify_api_secret)], tags=["pipeline"])
async def get_job_status(job_id: str):
    job = await _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Real-Time Streaming (SSE)
# ---------------------------------------------------------------------------

@app.get("/pipeline/stream/{pipeline_id}", tags=["streaming"])
async def stream_pipeline_events(pipeline_id: str):
    """
    Server-Sent Events stream for real-time pipeline progress.

    Connect via EventSource in the browser:
        const es = new EventSource('/pipeline/stream/<pipeline_id>');
        es.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    event_bus = get_event_bus()

    async def event_generator():
        yield f"event: connected\ndata: {{\"pipeline_id\": \"{pipeline_id}\"}}\n\n"
        try:
            async for event in event_bus.subscribe(
                topic="pipeline",
                pipeline_id=pipeline_id,
            ):
                yield event.to_sse()
                if event.event_type in ("pipeline_completed", "pipeline_failed"):
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/events/stream", tags=["streaming"])
async def stream_all_events(category: Optional[str] = None):
    """Stream all platform events (useful for monitoring dashboards)."""
    event_bus = get_event_bus()

    async def event_generator():
        yield "event: connected\ndata: {\"status\": \"streaming\"}\n\n"
        try:
            async for event in event_bus.subscribe(topic=category):
                yield event.to_sse()
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Memory & Analytics
# ---------------------------------------------------------------------------

@app.get("/analytics/agents", tags=["analytics"])
async def agent_performance():
    """Get performance profiles for all agents."""
    memory = get_memory_store()
    await memory.initialize()
    profiles = memory.get_all_profiles()
    return {
        agent_id: {
            "total_tasks": p.total_tasks,
            "success_rate": round(p.successful_tasks / max(p.total_tasks, 1), 3),
            "avg_quality": round(p.avg_quality_score, 3),
            "avg_duration_s": round(p.avg_duration_s, 2),
            "total_cost_usd": round(p.total_cost_usd, 4),
            "trend": p.trend,
            "model_performance": p.model_performance,
            "task_type_scores": p.task_type_scores,
        }
        for agent_id, p in profiles.items()
    }


@app.get("/analytics/metrics", tags=["analytics"])
async def platform_metrics():
    """Get aggregated platform metrics."""
    from events import MetricCollector
    event_bus = get_event_bus()
    collector = MetricCollector(event_bus)
    return collector.get_metrics()


@app.get("/analytics/events", tags=["analytics"])
async def recent_events(
    category: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    limit: int = 100,
):
    """Get recent event history."""
    event_bus = get_event_bus()
    cat = EventCategory(category) if category else None
    events = event_bus.get_history(category=cat, pipeline_id=pipeline_id, limit=limit)
    return [e.to_dict() for e in events]


@app.get("/memory/patterns/{agent_id}", tags=["memory"])
async def agent_patterns(agent_id: str, task_type: Optional[str] = None):
    """Get learned patterns for an agent."""
    memory = get_memory_store()
    await memory.initialize()
    patterns = memory.get_patterns(agent_id, task_type)
    return [
        {
            "pattern_id": p.pattern_id,
            "task_type": p.task_type,
            "description": p.description,
            "success_rate": p.success_rate,
            "sample_count": p.sample_count,
            "strategy": p.strategy,
        }
        for p in patterns
    ]


@app.post("/memory/extract-patterns/{agent_id}", tags=["memory"])
async def extract_patterns(agent_id: str, task_type: str = "pipeline_step"):
    """Trigger pattern extraction for an agent from episodic memory."""
    memory = get_memory_store()
    await memory.initialize()
    patterns = await memory.extract_patterns(agent_id, task_type)
    return {"extracted": len(patterns), "patterns": [p.pattern_id for p in patterns]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
