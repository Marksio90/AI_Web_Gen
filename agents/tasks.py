"""
Celery task definitions for async pipeline execution.

Queues:
  pipeline — full 6-agent pipeline per business
  crawler  — discovery batch jobs
  email    — outreach campaign batches
  default  — misc tasks
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from celery import Celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Celery app configuration
# ─────────────────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "ai_web_gen",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Warsaw",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,          # Fair distribution
    task_routes={
        "tasks.run_pipeline":       {"queue": "pipeline"},
        "tasks.run_pipeline_batch": {"queue": "pipeline"},
        "tasks.run_crawler":        {"queue": "crawler"},
        "tasks.send_campaign_batch":{"queue": "email"},
    },
    beat_schedule={
        # Auto-discover new businesses every night at 02:00 Warsaw time
        "nightly-discovery": {
            "task": "tasks.run_crawler",
            "schedule": 86400,  # every 24h
            "kwargs": {
                "cities": ["Warsaw", "Kraków", "Wrocław", "Gdańsk", "Poznań"],
                "categories": ["restaurant", "beauty_salon", "dental_clinic", "plumber"],
                "limit_per_city": 200,
            },
        },
        # Process ungenerated leads every 6 hours
        "process-pending-leads": {
            "task": "tasks.process_pending_leads",
            "schedule": 21600,
        },
    },
    broker_connection_retry_on_startup=True,
)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="tasks.run_pipeline",
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
)
def run_pipeline(self, business_data: dict) -> Optional[dict]:
    """
    Run the full 6-agent pipeline for a single business.
    Returns serialized ProcessedBusiness or None if skipped.
    """
    logger.info("Starting pipeline for: %s", business_data.get("name"))
    try:
        from pipeline import process_business
        result = _run_async(process_business(business_data))
        if result is None:
            logger.info("Business skipped (good website): %s", business_data.get("name"))
            return None
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.error("Pipeline failed for %s: %s", business_data.get("name"), exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="tasks.run_pipeline_batch",
    max_retries=1,
    soft_time_limit=3600,
    time_limit=3900,
)
def run_pipeline_batch(self, businesses: list[dict], concurrency: int = 5) -> dict:
    """Process a batch of businesses with controlled concurrency."""
    logger.info("Starting batch pipeline: %d businesses", len(businesses))
    try:
        from pipeline import process_batch
        results = _run_async(process_batch(businesses, concurrency))
        return {
            "processed": len(results),
            "total": len(businesses),
            "results": [r.model_dump(mode="json") for r in results],
        }
    except Exception as exc:
        logger.error("Batch pipeline failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="tasks.run_crawler",
    max_retries=3,
    default_retry_delay=120,
    soft_time_limit=1800,
)
def run_crawler(
    self,
    cities: list[str],
    categories: list[str],
    limit_per_city: int = 200,
    source: str = "both",
) -> dict:
    """
    Discover businesses and POST them to the Next.js platform API.
    Runs nightly via Celery Beat.
    """
    import asyncio
    from crawler.discover import GooglePlacesCrawler, OSMCrawler, POLISH_CITIES
    import httpx
    import os

    platform_url = os.getenv("PLATFORM_API_URL", "http://platform:3000")
    google_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    total_discovered = 0

    async def _discover():
        nonlocal total_discovered
        for city_name in cities:
            city_data = next((c for c in POLISH_CITIES if c[0].lower() == city_name.lower()), None)
            (lat, lng) = (city_data[1], city_data[2]) if city_data else (52.2297, 21.0122)

            for category in categories:
                discovered = []

                if source in ("google", "both") and google_key:
                    crawler = GooglePlacesCrawler(google_key)
                    places = await crawler.discover_city(city_name, lat, lng, category, limit_per_city)
                    await crawler.close()
                    discovered.extend(places)

                if source in ("osm", "both"):
                    osm = OSMCrawler()
                    try:
                        osm_places = await osm.query(city_name, category)
                        discovered.extend(osm_places)
                    except Exception as e:
                        logger.warning("OSM query failed for %s/%s: %s", city_name, category, e)
                    finally:
                        await osm.close()

                # Deduplicate
                seen, unique = set(), []
                for b in discovered:
                    key = (b["name"].lower().strip(), b["city"].lower())
                    if key not in seen and b["name"]:
                        seen.add(key)
                        unique.append(b)

                # POST to platform API
                api_secret = os.getenv("AGENT_API_SECRET", "")
                auth_headers = {"Content-Type": "application/json"}
                if api_secret:
                    auth_headers["X-Api-Secret"] = api_secret
                async with httpx.AsyncClient(timeout=30) as client:
                    for business in unique:
                        try:
                            await client.post(
                                f"{platform_url}/api/leads",
                                json=business,
                                headers=auth_headers,
                            )
                            total_discovered += 1
                        except Exception as e:
                            logger.debug("Failed to POST lead: %s", e)

                logger.info(
                    "Discovered: %s / %s → %d businesses",
                    city_name, category, len(unique),
                )

    _run_async(_discover())
    logger.info("Crawler complete: %d total businesses discovered", total_discovered)
    return {"total_discovered": total_discovered}


@celery_app.task(
    bind=True,
    name="tasks.process_pending_leads",
    soft_time_limit=3600,
)
def process_pending_leads(self, limit: int = 100) -> dict:
    """
    Fetch unprocessed leads from the platform API and run the pipeline.
    Called automatically every 6 hours via Celery Beat.
    """
    import httpx
    import os

    platform_url = os.getenv("PLATFORM_API_URL", "http://platform:3000")

    async def _run():
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{platform_url}/api/leads",
                params={"stage": "DISCOVERED", "limit": limit},
            )
            leads = resp.json().get("leads", [])
            logger.info("Processing %d pending leads", len(leads))

            for lead in leads:
                # Trigger generation via platform API (which calls agents)
                try:
                    await client.post(
                        f"{platform_url}/api/leads/{lead['id']}/generate",
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as e:
                    logger.warning("Failed to trigger generation for %s: %s", lead["id"], e)

        return {"processed": len(leads)}

    return _run_async(_run())


@celery_app.task(
    bind=True,
    name="tasks.send_campaign_batch",
    soft_time_limit=600,
)
def send_campaign_batch(self, campaign_id: str, batch_size: int = 20) -> dict:
    """Trigger email send for a campaign batch via the platform API."""
    import httpx
    import os

    platform_url = os.getenv("PLATFORM_API_URL", "http://platform:3000")

    async def _run():
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{platform_url}/api/campaigns/{campaign_id}/send",
                json={"batchSize": batch_size},
            )
            return resp.json()

    return _run_async(_run())
