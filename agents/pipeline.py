"""
Main orchestration pipeline — processes one business through all 6 agents.

Usage:
    python pipeline.py --input businesses.jsonl --output results.jsonl
    python pipeline.py --business-id <place_id>
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Optional

import structlog
import typer
from agents import Runner
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents_def import (
    content_agent,
    crawler_agent,
    design_agent,
    email_agent,
    qc_agent,
    seo_agent,
)
from config import settings
from models import BusinessData, ProcessedBusiness, WebsiteStatus

log = structlog.get_logger()
app = typer.Typer()


# ---------------------------------------------------------------------------
# Cost estimation helpers
# ---------------------------------------------------------------------------
COST_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o":      {"input": 2.50, "output": 10.00},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_1M.get(model, {"input": 2.5, "output": 10.0})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def _parse_agent_json(raw: str) -> dict:
    """Parse JSON from agent output, stripping markdown code fences if present."""
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def _run_agent(agent, prompt: str):
    """Run an agent with automatic retry on transient failures."""
    return await Runner.run(agent, prompt)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------
async def process_business(business_raw: dict) -> Optional[ProcessedBusiness]:
    """Run a single business through the complete 6-agent pipeline."""
    start = time.monotonic()
    total_cost = 0.0

    try:
        # --- Step 1: Crawler Agent — extract & normalize data ---
        log.info("crawler.start", name=business_raw.get("name"))
        crawl_result = await _run_agent(
            crawler_agent,
            f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}"
        )
        business = BusinessData(**_parse_agent_json(crawl_result.final_output))
        log.info("crawler.done", name=business.name, status=business.website_url)

        # --- Step 2: SEO Agent — analyze existing website (if any) ---
        if business.website_url:
            log.info("seo.start", url=business.website_url)
            seo_result = await _run_agent(
                seo_agent,
                f"Analyze website quality for: {business.name} ({business.category})\n"
                f"URL: {business.website_url}\n"
                f"Location: {business.city}, Poland"
            )
            seo_analysis = _parse_agent_json(seo_result.final_output)
            seo_analysis["business_id"] = business.place_id
        else:
            # No website — instant lead
            seo_analysis = {
                "business_id": business.place_id,
                "website_status": WebsiteStatus.NONE,
                "analysis_notes": "No website found — prime target for outreach",
            }

        # Skip businesses with good websites
        if seo_analysis.get("website_status") == WebsiteStatus.GOOD:
            log.info("skip.good_website", name=business.name)
            return None

        # --- Step 3: Design Agent — select template & style ---
        log.info("design.start", name=business.name)
        design_result = await _run_agent(
            design_agent,
            f"Select design for:\n"
            f"Business: {business.name}\n"
            f"Category: {business.category}\n"
            f"City: {business.city}\n"
            f"SEO notes: {seo_analysis.get('analysis_notes', '')}"
        )
        design_spec = _parse_agent_json(design_result.final_output)

        # --- Step 4: Content Agent (with QC retry loop) ---
        content_prompt = (
            f"Stwórz treści strony dla:\n"
            f"Firma: {business.name}\n"
            f"Kategoria: {business.category}\n"
            f"Miasto: {business.city}\n"
            f"Adres: {business.address}\n"
            f"Telefon: {business.phone or 'brak'}\n"
            f"Ocena Google: {business.rating or 'brak'} ({business.review_count or 0} opinii)\n"
            f"Szablon: {design_spec.get('template_id')}\n"
            f"Styl: {design_spec.get('style_mood')}\n"
            f"Sekcje: {', '.join(design_spec.get('sections', []))}"
        )

        approved = False
        content = None
        for attempt in range(settings.max_qc_retries):
            log.info("content.generate", name=business.name, attempt=attempt + 1)
            content_result = await _run_agent(content_agent, content_prompt)
            content = _parse_agent_json(content_result.final_output)
            content["business_id"] = business.place_id

            # QC review
            qc_input = (
                f"Review this generated website content:\n"
                f"Business: {business.name} ({business.category}, {business.city})\n"
                f"Design: {json.dumps(design_spec)}\n"
                f"Content: {json.dumps(content, ensure_ascii=False)}\n"
                f"Iteration: {attempt + 1}"
            )
            qc_result = await _run_agent(qc_agent, qc_input)
            qc_data = _parse_agent_json(qc_result.final_output)
            qc_data["business_id"] = business.place_id
            qc_data["iteration"] = attempt + 1

            if qc_data.get("approved"):
                log.info("qc.approved", name=business.name, score=qc_data.get("overall_score"))
                approved = True
                break
            else:
                log.warning("qc.revision", issues=qc_data.get("issues", []))
                # Feed issues back into next content prompt
                content_prompt += (
                    f"\n\nPOPRAWKI (iteracja {attempt + 1}):\n"
                    + "\n".join(f"- {i}" for i in qc_data.get("issues", []))
                )

        if not approved:
            log.warning("qc.max_retries", name=business.name)
            # Proceed with best available content

        # --- Step 5: Email Outreach Agent ---
        recipient_email = business.email
        if not recipient_email:
            # Construct likely generic email from website domain
            if business.website_url:
                from urllib.parse import urlparse
                domain = urlparse(business.website_url).netloc.lstrip("www.")
                recipient_email = f"kontakt@{domain}"
            else:
                log.warning("no_email", name=business.name)
                recipient_email = None

        if recipient_email:
            from tools import generate_slug
            slug = generate_slug(business.name, business.city)
            demo_url = f"https://{slug}.{settings.demo_base_domain}"

            log.info("email.generate", name=business.name, email=recipient_email)
            email_result = await _run_agent(
                email_agent,
                f"Generate 3 outreach email variants for:\n"
                f"Business: {business.name}\n"
                f"Category: {business.category}\n"
                f"City: {business.city}\n"
                f"Recipient email: {recipient_email}\n"
                f"Demo URL: {demo_url}\n"
                f"Website status: {seo_analysis.get('website_status')}"
            )
            outreach_data = _parse_agent_json(email_result.final_output)
            outreach_data["business_id"] = business.place_id
            outreach_data["recipient_email"] = recipient_email
            outreach_data["demo_url"] = demo_url
        else:
            outreach_data = None

        duration = time.monotonic() - start
        log.info("pipeline.complete", name=business.name, duration_s=round(duration, 2))

        return ProcessedBusiness(
            business=business,
            seo_analysis=seo_analysis,
            design_spec=design_spec,
            content=content,
            qc_result=qc_data,
            outreach_email=outreach_data,
            pipeline_duration_s=round(duration, 2),
        )

    except Exception as exc:
        log.error("pipeline.error", name=business_raw.get("name"), error=str(exc))
        raise


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
async def process_batch(businesses: list[dict], concurrency: int = 5) -> list[ProcessedBusiness]:
    """Process multiple businesses with controlled concurrency."""
    concurrency = max(1, min(concurrency, settings.max_concurrent_agents))
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process_with_sem(b: dict):
        async with semaphore:
            return await process_business(b)

    tasks = [process_with_sem(b) for b in businesses]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for item in raw:
        if isinstance(item, Exception):
            log.error("batch.item_error", error=str(item))
        elif item is not None:
            results.append(item)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@app.command()
def run_pipeline(
    input_file: str = typer.Option("businesses.jsonl", "--input", "-i"),
    output_file: str = typer.Option("results.jsonl", "--output", "-o"),
    concurrency: int = typer.Option(5, "--concurrency", "-c"),
    limit: int = typer.Option(0, "--limit", "-l", help="0 = no limit"),
):
    """Process businesses from a JSONL input file."""
    with open(input_file) as f:
        businesses = [json.loads(line) for line in f if line.strip()]

    if limit:
        businesses = businesses[:limit]

    typer.echo(f"Processing {len(businesses)} businesses (concurrency={concurrency})")
    results = asyncio.run(process_batch(businesses, concurrency))

    with open(output_file, "w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    typer.echo(f"Done. {len(results)} processed → {output_file}")


if __name__ == "__main__":
    app()
