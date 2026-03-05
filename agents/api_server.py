"""
FastAPI server that exposes the agent pipeline as an HTTP API.
Called by the Next.js platform when generating demo sites for leads.

Run:
    uvicorn api_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from pipeline import process_business
from models import ProcessedBusiness

app = FastAPI(
    title="AI Web Generator — Agent API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENV") != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourplatform.pl", "http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# In-memory job tracking (use Redis in production)
_jobs: dict[str, dict] = {}


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


def _verify_secret(x_api_secret: Optional[str] = Header(None)) -> None:
    expected = settings.__dict__.get("agent_api_secret") or os.getenv("AGENT_API_SECRET", "")
    if expected and x_api_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/process", response_model=ProcessResponse)
async def process(
    request: ProcessRequest,
    x_api_secret: Optional[str] = Header(None),
):
    """Synchronously process a single business through the full 6-agent pipeline."""
    _verify_secret(x_api_secret)

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
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class BatchRequest(BaseModel):
    businesses: list[ProcessRequest]
    concurrency: int = 5


class BatchJobResponse(BaseModel):
    job_id: str
    total: int
    status: str = "queued"


@app.post("/process/batch", response_model=BatchJobResponse)
async def process_batch_async(
    request: BatchRequest,
    background_tasks: BackgroundTasks,
    x_api_secret: Optional[str] = Header(None),
):
    """Queue a batch of businesses for async processing."""
    _verify_secret(x_api_secret)

    import uuid
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "total": len(request.businesses), "completed": 0, "results": []}

    async def run_batch():
        from pipeline import process_batch
        results = await process_batch(
            [b.model_dump() for b in request.businesses],
            request.concurrency,
        )
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["completed"] = len(results)
        _jobs[job_id]["results"] = [r.model_dump() for r in results]

    background_tasks.add_task(run_batch)

    return BatchJobResponse(job_id=job_id, total=len(request.businesses))


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, x_api_secret: Optional[str] = Header(None)):
    _verify_secret(x_api_secret)
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
