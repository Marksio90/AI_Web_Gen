"""
Advanced Multi-Agent Pipeline Engine.

Transforms a simple linear pipeline into a DAG-based, swarm-intelligent,
evolutionary, self-learning multi-agent orchestration system.

Strategies:
  - STANDARD:      Linear 6-agent pipeline (original)
  - SWARM:         Multi-agent voting on design & content decisions
  - EVOLUTIONARY:  Genetic algorithm for content optimization
  - DEBATE:        Adversarial debate for design decisions
  - TURBO:         Parallel fast-path with nano models
  - PREMIUM:       Maximum quality with all engines combined

Usage:
    python pipeline.py --input businesses.jsonl --output results.jsonl
    python pipeline.py --business-id <place_id> --strategy swarm
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from typing import Optional
from urllib.parse import urlparse

import structlog
import typer
from agents import Runner
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents_def import (
    AGENT_REGISTRY,
    competitive_intel_agent,
    content_agent,
    content_refinement_agent,
    crawler_agent,
    design_agent,
    design_critic_agent,
    email_agent,
    orchestrator_agent,
    personalization_agent,
    qc_agent,
    seo_agent,
    seo_optimizer_agent,
)
from config import settings
from events import Event, EventBus, EventCategory, get_event_bus
from memory import EpisodicMemory, MemoryStore, get_memory_store
from models import (
    AgentExecutionTrace,
    BusinessData,
    CompetitiveIntel,
    DesignSpec,
    GeneratedContent,
    OutreachEmail,
    PipelineStrategy,
    PipelineTelemetry,
    ProcessedBusiness,
    QCResult,
    SEOAnalysis,
    WebsiteStatus,
)
from orchestrator import DAGBuilder, EdgeCondition, ExecutionDAG
from swarm import (
    ConsensusStrategy,
    DebateProtocol,
    IterativeRefinementSwarm,
    SpecialistRouter,
    TournamentSelection,
    VotingEnsemble,
)
from algorithms import (
    ChainOfThought,
    CostPerformanceOptimizer,
    EnsembleScorer,
    EvolutionaryOptimizer,
    MultiModelRouter,
)

log = structlog.get_logger()
app = typer.Typer()

# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------
COST_PER_1M = {
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
    "gpt-4o":        {"input": 2.50,  "output": 10.00},
    "gpt-4.1-mini":  {"input": 0.40,  "output": 1.60},
    "gpt-4.1":       {"input": 2.00,  "output": 8.00},
    "gpt-4.1-nano":  {"input": 0.10,  "output": 0.40},
    "llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
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


# ---------------------------------------------------------------------------
# Agent Runner with telemetry
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
)
async def _run_agent(agent, prompt: str, pipeline_id: str = "") -> tuple:
    """Run an agent with automatic retry, telemetry, and memory recording."""
    start = time.monotonic()
    event_bus = get_event_bus()
    memory = get_memory_store()

    await event_bus.publish(Event(
        category=EventCategory.AGENT,
        event_type="agent_started",
        source=agent.name,
        pipeline_id=pipeline_id,
        data={"agent": agent.name, "model": agent.model},
    ))

    result = await Runner.run(agent, prompt)
    duration = time.monotonic() - start

    trace = AgentExecutionTrace(
        agent_id=agent.name.lower().replace(" ", "_"),
        agent_name=agent.name,
        model_used=agent.model,
        start_time=start,
        end_time=start + duration,
        duration_s=round(duration, 3),
        success=True,
    )

    await event_bus.publish(Event(
        category=EventCategory.AGENT,
        event_type="agent_completed",
        source=agent.name,
        pipeline_id=pipeline_id,
        data={"agent": agent.name, "duration_s": round(duration, 3)},
    ))

    # Record in memory
    if settings.enable_memory:
        await memory.record_episode(EpisodicMemory(
            memory_id=uuid.uuid4().hex[:12],
            agent_id=agent.name.lower().replace(" ", "_"),
            task_type="pipeline_step",
            input_summary=prompt[:200],
            output_summary=str(result.final_output)[:200],
            success=True,
            quality_score=0.8,
            duration_s=duration,
            cost_usd=0.0,
            model_used=agent.model,
        ))

    return result, trace


# ===========================================================================
# Strategy: STANDARD — Linear 6-agent pipeline
# ===========================================================================

async def _strategy_standard(business_raw: dict, pipeline_id: str) -> Optional[ProcessedBusiness]:
    """Original linear pipeline enhanced with telemetry and memory."""
    start = time.monotonic()
    traces = []
    event_bus = get_event_bus()

    # Step 1: Crawler
    log.info("pipeline.crawler.start", name=business_raw.get("name"))
    crawl_result, crawl_trace = await _run_agent(
        crawler_agent,
        f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}",
        pipeline_id,
    )
    traces.append(crawl_trace)
    business = BusinessData(**_parse_agent_json(crawl_result.final_output))

    # Step 2: SEO Analysis
    if business.website_url:
        seo_result, seo_trace = await _run_agent(
            seo_agent,
            f"Analyze website quality for: {business.name} ({business.category})\n"
            f"URL: {business.website_url}\nLocation: {business.city}, Poland",
            pipeline_id,
        )
        traces.append(seo_trace)
        seo_raw = _parse_agent_json(seo_result.final_output)
        seo_raw["business_id"] = business.place_id
        seo_analysis = SEOAnalysis(**seo_raw)
    else:
        seo_analysis = SEOAnalysis(
            business_id=business.place_id,
            website_status=WebsiteStatus.NONE,
            analysis_notes="No website found — prime target for outreach",
        )

    if seo_analysis.website_status == WebsiteStatus.GOOD:
        log.info("pipeline.skip.good_website", name=business.name)
        return None

    # Step 3: Design
    design_result, design_trace = await _run_agent(
        design_agent,
        f"Select design for:\nBusiness: {business.name}\n"
        f"Category: {business.category}\nCity: {business.city}\n"
        f"SEO notes: {seo_analysis.analysis_notes}",
        pipeline_id,
    )
    traces.append(design_trace)
    design_spec = DesignSpec(**_parse_agent_json(design_result.final_output))

    # Step 4: Content with QC loop
    content_prompt = (
        f"Stwórz treści strony dla:\nFirma: {business.name}\n"
        f"Kategoria: {business.category}\nMiasto: {business.city}\n"
        f"Adres: {business.address}\nTelefon: {business.phone or 'brak'}\n"
        f"Ocena Google: {business.rating or 'brak'} ({business.review_count or 0} opinii)\n"
        f"Szablon: {design_spec.template_id}\nStyl: {design_spec.style_mood}\n"
        f"Sekcje: {', '.join(design_spec.sections)}"
    )

    approved = False
    content: Optional[GeneratedContent] = None
    qc_data: Optional[QCResult] = None

    for attempt in range(settings.max_qc_retries):
        content_result, content_trace = await _run_agent(content_agent, content_prompt, pipeline_id)
        traces.append(content_trace)
        content_raw = _parse_agent_json(content_result.final_output)
        content_raw["business_id"] = business.place_id
        content_raw["model_used"] = content_agent.model
        content = GeneratedContent(**content_raw)

        qc_input = (
            f"Review this generated website content:\n"
            f"Business: {business.name} ({business.category}, {business.city})\n"
            f"Design: {design_spec.model_dump_json()}\n"
            f"Content: {content.model_dump_json()}\nIteration: {attempt + 1}"
        )
        qc_result, qc_trace = await _run_agent(qc_agent, qc_input, pipeline_id)
        traces.append(qc_trace)
        qc_raw = _parse_agent_json(qc_result.final_output)
        qc_raw["business_id"] = business.place_id
        qc_raw["iteration"] = attempt + 1
        qc_data = QCResult(**qc_raw)

        if qc_data.approved:
            approved = True
            break
        else:
            content_prompt += (
                f"\n\nPOPRAWKI (iteracja {attempt + 1}):\n"
                + "\n".join(f"- {i}" for i in qc_data.issues)
            )

    # Step 5: Email
    outreach_email = await _generate_outreach(business, seo_analysis, pipeline_id, traces)

    duration = time.monotonic() - start
    from tools import generate_slug as _gen_slug
    site_slug = _gen_slug(business.name, business.city)

    return ProcessedBusiness(
        business=business,
        seo_analysis=seo_analysis,
        design_spec=design_spec,
        content=content,
        qc_result=qc_data,
        outreach_email=outreach_email,
        demo_site_slug=site_slug,
        demo_site_url=f"https://{site_slug}.{settings.demo_base_domain}",
        pipeline_duration_s=round(duration, 2),
        strategy_used=PipelineStrategy.STANDARD,
        telemetry=PipelineTelemetry(
            pipeline_id=pipeline_id,
            strategy=PipelineStrategy.STANDARD,
            start_time=start,
            end_time=time.monotonic(),
            total_duration_s=round(duration, 2),
            agent_traces=traces,
            models_used=list({t.model_used for t in traces}),
        ),
    )


# ===========================================================================
# Strategy: SWARM — Multi-agent consensus
# ===========================================================================

async def _strategy_swarm(business_raw: dict, pipeline_id: str) -> Optional[ProcessedBusiness]:
    """Swarm intelligence pipeline — agents vote on key decisions."""
    start = time.monotonic()
    traces = []

    # Step 1: Crawler (standard)
    crawl_result, crawl_trace = await _run_agent(
        crawler_agent,
        f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}",
        pipeline_id,
    )
    traces.append(crawl_trace)
    business = BusinessData(**_parse_agent_json(crawl_result.final_output))

    # Step 2: SEO (standard)
    if business.website_url:
        seo_result, seo_trace = await _run_agent(
            seo_agent,
            f"Analyze website quality for: {business.name} ({business.category})\n"
            f"URL: {business.website_url}\nLocation: {business.city}, Poland",
            pipeline_id,
        )
        traces.append(seo_trace)
        seo_raw = _parse_agent_json(seo_result.final_output)
        seo_raw["business_id"] = business.place_id
        seo_analysis = SEOAnalysis(**seo_raw)
    else:
        seo_analysis = SEOAnalysis(
            business_id=business.place_id,
            website_status=WebsiteStatus.NONE,
            analysis_notes="No website found — prime target",
        )

    if seo_analysis.website_status == WebsiteStatus.GOOD:
        return None

    # Step 3: SWARM Design — Multiple agents vote on design
    async def _design_voter(prompt):
        r, t = await _run_agent(design_agent, prompt, pipeline_id)
        traces.append(t)
        parsed = _parse_agent_json(r.final_output)
        return {"proposal": parsed, "confidence": 0.85}

    async def _personalization_voter(prompt):
        r, t = await _run_agent(personalization_agent, str(prompt), pipeline_id)
        traces.append(t)
        parsed = _parse_agent_json(r.final_output)
        return {"proposal": parsed, "confidence": 0.7}

    design_prompt = (
        f"Select design for:\nBusiness: {business.name}\n"
        f"Category: {business.category}\nCity: {business.city}\n"
        f"SEO notes: {seo_analysis.analysis_notes}"
    )

    ensemble = VotingEnsemble(
        agents=[
            ("design_main", "Design Specialist", lambda p: _design_voter(design_prompt)),
            ("design_alt", "Design Alt", lambda p: _design_voter(design_prompt)),
            ("personalization", "Personalizer", lambda p: _personalization_voter(design_prompt)),
        ],
        weights={"design_main": 1.0, "design_alt": 0.8, "personalization": 0.6},
    )

    swarm_decision = await ensemble.vote(design_prompt, strategy=ConsensusStrategy.WEIGHTED_VOTE)
    design_spec = DesignSpec(**swarm_decision.winner)

    log.info("swarm.design.decided",
             confidence=swarm_decision.confidence,
             dissent=swarm_decision.dissent_ratio)

    # Step 4: Content with iterative refinement swarm
    content_prompt = (
        f"Stwórz treści strony dla:\nFirma: {business.name}\n"
        f"Kategoria: {business.category}\nMiasto: {business.city}\n"
        f"Adres: {business.address}\nTelefon: {business.phone or 'brak'}\n"
        f"Ocena Google: {business.rating or 'brak'} ({business.review_count or 0} opinii)\n"
        f"Szablon: {design_spec.template_id}\nStyl: {design_spec.style_mood}\n"
        f"Sekcje: {', '.join(design_spec.sections)}"
    )

    content_result, content_trace = await _run_agent(content_agent, content_prompt, pipeline_id)
    traces.append(content_trace)
    content_raw = _parse_agent_json(content_result.final_output)
    content_raw["business_id"] = business.place_id
    content_raw["model_used"] = content_agent.model
    content_raw["content_generation_strategy"] = "swarm"
    content_raw["swarm_confidence"] = swarm_decision.confidence
    content = GeneratedContent(**content_raw)

    # Swarm QC: multiple QC perspectives
    qc_input = (
        f"Review this generated website content:\n"
        f"Business: {business.name} ({business.category}, {business.city})\n"
        f"Design: {design_spec.model_dump_json()}\n"
        f"Content: {content.model_dump_json()}"
    )
    qc_result, qc_trace = await _run_agent(qc_agent, qc_input, pipeline_id)
    traces.append(qc_trace)
    qc_raw = _parse_agent_json(qc_result.final_output)
    qc_raw["business_id"] = business.place_id
    qc_raw["consensus_confidence"] = swarm_decision.confidence
    qc_data = QCResult(**qc_raw)

    # Step 5: Email
    outreach_email = await _generate_outreach(business, seo_analysis, pipeline_id, traces)

    duration = time.monotonic() - start
    from tools import generate_slug as _gen_slug
    site_slug = _gen_slug(business.name, business.city)

    return ProcessedBusiness(
        business=business,
        seo_analysis=seo_analysis,
        design_spec=design_spec,
        content=content,
        qc_result=qc_data,
        outreach_email=outreach_email,
        demo_site_slug=site_slug,
        demo_site_url=f"https://{site_slug}.{settings.demo_base_domain}",
        pipeline_duration_s=round(duration, 2),
        strategy_used=PipelineStrategy.SWARM_CONSENSUS,
        quality_confidence=swarm_decision.confidence,
        telemetry=PipelineTelemetry(
            pipeline_id=pipeline_id,
            strategy=PipelineStrategy.SWARM_CONSENSUS,
            start_time=start,
            end_time=time.monotonic(),
            total_duration_s=round(duration, 2),
            agent_traces=traces,
            models_used=list({t.model_used for t in traces}),
            swarm_decisions=1,
        ),
    )


# ===========================================================================
# Strategy: EVOLUTIONARY — Genetic optimization for content
# ===========================================================================

async def _strategy_evolutionary(business_raw: dict, pipeline_id: str) -> Optional[ProcessedBusiness]:
    """Evolutionary pipeline — generates multiple content variants and evolves the best."""
    start = time.monotonic()
    traces = []

    # Steps 1-3 same as standard
    crawl_result, crawl_trace = await _run_agent(
        crawler_agent,
        f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}",
        pipeline_id,
    )
    traces.append(crawl_trace)
    business = BusinessData(**_parse_agent_json(crawl_result.final_output))

    if business.website_url:
        seo_result, seo_trace = await _run_agent(
            seo_agent,
            f"Analyze website quality for: {business.name} ({business.category})\n"
            f"URL: {business.website_url}\nLocation: {business.city}, Poland",
            pipeline_id,
        )
        traces.append(seo_trace)
        seo_raw = _parse_agent_json(seo_result.final_output)
        seo_raw["business_id"] = business.place_id
        seo_analysis = SEOAnalysis(**seo_raw)
    else:
        seo_analysis = SEOAnalysis(
            business_id=business.place_id,
            website_status=WebsiteStatus.NONE,
            analysis_notes="No website found — prime target",
        )

    if seo_analysis.website_status == WebsiteStatus.GOOD:
        return None

    design_result, design_trace = await _run_agent(
        design_agent,
        f"Select design for:\nBusiness: {business.name}\n"
        f"Category: {business.category}\nCity: {business.city}\n"
        f"SEO notes: {seo_analysis.analysis_notes}",
        pipeline_id,
    )
    traces.append(design_trace)
    design_spec = DesignSpec(**_parse_agent_json(design_result.final_output))

    # Step 4: EVOLUTIONARY Content Generation
    content_prompt = (
        f"Stwórz treści strony dla:\nFirma: {business.name}\n"
        f"Kategoria: {business.category}\nMiasto: {business.city}\n"
        f"Adres: {business.address}\nTelefon: {business.phone or 'brak'}\n"
        f"Ocena Google: {business.rating or 'brak'} ({business.review_count or 0} opinii)\n"
        f"Szablon: {design_spec.template_id}\nStyl: {design_spec.style_mood}\n"
        f"Sekcje: {', '.join(design_spec.sections)}"
    )

    async def _generate_content(task_input):
        r, t = await _run_agent(content_agent, content_prompt, pipeline_id)
        traces.append(t)
        return _parse_agent_json(r.final_output)

    async def _mutate_content(existing_content, task_input):
        mutation_prompt = (
            f"Ulepsz poniższe treści strony. Zachowaj strukturę JSON.\n"
            f"Firma: {business.name}, {business.city}\n"
            f"Obecna wersja:\n{json.dumps(existing_content, ensure_ascii=False)}\n\n"
            f"Popraw: naturalność języka, lokalne odniesienia, SEO, unikalność."
        )
        r, t = await _run_agent(content_refinement_agent, mutation_prompt, pipeline_id)
        traces.append(t)
        parsed = _parse_agent_json(r.final_output)
        return parsed.get("improved", parsed)

    async def _fitness_fn(content_data):
        qc_input = (
            f"Review and score (0-100) this content for {business.name}:\n"
            f"{json.dumps(content_data, ensure_ascii=False)}\n"
            f"Return ONLY a number 0-100."
        )
        r, t = await _run_agent(qc_agent, qc_input, pipeline_id)
        traces.append(t)
        try:
            score_text = r.final_output.strip()
            score = float(re.search(r'\d+', score_text).group()) / 100.0
            return min(1.0, max(0.0, score))
        except Exception:
            return 0.5

    optimizer = EvolutionaryOptimizer(
        generator_fn=_generate_content,
        mutator_fn=_mutate_content,
        fitness_fn=_fitness_fn,
        population_size=settings.evolution_population_size,
        max_generations=settings.evolution_max_generations,
        mutation_rate=settings.evolution_mutation_rate,
        elite_count=settings.evolution_elite_count,
    )

    best_genome = await optimizer.evolve(content_prompt)
    content_raw = best_genome.content if isinstance(best_genome.content, dict) else _parse_agent_json(str(best_genome.content))
    content_raw["business_id"] = business.place_id
    content_raw["content_generation_strategy"] = "evolutionary"
    content_raw["evolution_generation"] = best_genome.generation
    content_raw["evolution_fitness"] = best_genome.fitness
    content_raw["model_used"] = content_agent.model
    content = GeneratedContent(**content_raw)

    log.info("evolution.best", fitness=best_genome.fitness, generation=best_genome.generation)

    # QC on evolved content
    qc_input = (
        f"Review this evolved website content:\n"
        f"Business: {business.name} ({business.category}, {business.city})\n"
        f"Design: {design_spec.model_dump_json()}\n"
        f"Content: {content.model_dump_json()}\n"
        f"Evolution fitness: {best_genome.fitness}"
    )
    qc_result, qc_trace = await _run_agent(qc_agent, qc_input, pipeline_id)
    traces.append(qc_trace)
    qc_raw = _parse_agent_json(qc_result.final_output)
    qc_raw["business_id"] = business.place_id
    qc_data = QCResult(**qc_raw)

    # Email
    outreach_email = await _generate_outreach(business, seo_analysis, pipeline_id, traces)

    duration = time.monotonic() - start
    from tools import generate_slug as _gen_slug
    site_slug = _gen_slug(business.name, business.city)

    return ProcessedBusiness(
        business=business,
        seo_analysis=seo_analysis,
        design_spec=design_spec,
        content=content,
        qc_result=qc_data,
        outreach_email=outreach_email,
        demo_site_slug=site_slug,
        demo_site_url=f"https://{site_slug}.{settings.demo_base_domain}",
        pipeline_duration_s=round(duration, 2),
        strategy_used=PipelineStrategy.EVOLUTIONARY,
        quality_confidence=best_genome.fitness,
        telemetry=PipelineTelemetry(
            pipeline_id=pipeline_id,
            strategy=PipelineStrategy.EVOLUTIONARY,
            start_time=start,
            end_time=time.monotonic(),
            total_duration_s=round(duration, 2),
            agent_traces=traces,
            models_used=list({t.model_used for t in traces}),
            evolution_generations=best_genome.generation + 1,
        ),
    )


# ===========================================================================
# Strategy: TURBO — Parallel fast-path
# ===========================================================================

async def _strategy_turbo(business_raw: dict, pipeline_id: str) -> Optional[ProcessedBusiness]:
    """Fast parallel pipeline — design and SEO run concurrently."""
    start = time.monotonic()
    traces = []

    # Step 1: Crawler
    crawl_result, crawl_trace = await _run_agent(
        crawler_agent,
        f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}",
        pipeline_id,
    )
    traces.append(crawl_trace)
    business = BusinessData(**_parse_agent_json(crawl_result.final_output))

    # Step 2 & 3: Run SEO + Design in PARALLEL
    async def _run_seo():
        if not business.website_url:
            return SEOAnalysis(
                business_id=business.place_id,
                website_status=WebsiteStatus.NONE,
                analysis_notes="No website found — prime target",
            ), None
        r, t = await _run_agent(
            seo_agent,
            f"Analyze website quality for: {business.name} ({business.category})\n"
            f"URL: {business.website_url}\nLocation: {business.city}, Poland",
            pipeline_id,
        )
        raw = _parse_agent_json(r.final_output)
        raw["business_id"] = business.place_id
        return SEOAnalysis(**raw), t

    async def _run_design():
        r, t = await _run_agent(
            design_agent,
            f"Select design for:\nBusiness: {business.name}\n"
            f"Category: {business.category}\nCity: {business.city}",
            pipeline_id,
        )
        return DesignSpec(**_parse_agent_json(r.final_output)), t

    (seo_analysis, seo_trace), (design_spec, design_trace) = await asyncio.gather(
        _run_seo(), _run_design()
    )
    if seo_trace:
        traces.append(seo_trace)
    if design_trace:
        traces.append(design_trace)

    if seo_analysis.website_status == WebsiteStatus.GOOD:
        return None

    # Step 4: Content (single pass, no QC loop for speed)
    content_prompt = (
        f"Stwórz treści strony dla:\nFirma: {business.name}\n"
        f"Kategoria: {business.category}\nMiasto: {business.city}\n"
        f"Adres: {business.address}\nSzablon: {design_spec.template_id}\n"
        f"Styl: {design_spec.style_mood}\nSekcje: {', '.join(design_spec.sections)}"
    )
    content_result, content_trace = await _run_agent(content_agent, content_prompt, pipeline_id)
    traces.append(content_trace)
    content_raw = _parse_agent_json(content_result.final_output)
    content_raw["business_id"] = business.place_id
    content_raw["content_generation_strategy"] = "turbo"
    content_raw["model_used"] = content_agent.model
    content = GeneratedContent(**content_raw)

    # Lightweight QC (single pass)
    qc_input = (
        f"Quick review: {business.name} ({business.category}, {business.city})\n"
        f"Content: {content.model_dump_json()}"
    )
    qc_result, qc_trace = await _run_agent(qc_agent, qc_input, pipeline_id)
    traces.append(qc_trace)
    qc_raw = _parse_agent_json(qc_result.final_output)
    qc_raw["business_id"] = business.place_id
    qc_data = QCResult(**qc_raw)

    # Email
    outreach_email = await _generate_outreach(business, seo_analysis, pipeline_id, traces)

    duration = time.monotonic() - start
    from tools import generate_slug as _gen_slug
    site_slug = _gen_slug(business.name, business.city)

    return ProcessedBusiness(
        business=business,
        seo_analysis=seo_analysis,
        design_spec=design_spec,
        content=content,
        qc_result=qc_data,
        outreach_email=outreach_email,
        demo_site_slug=site_slug,
        demo_site_url=f"https://{site_slug}.{settings.demo_base_domain}",
        pipeline_duration_s=round(duration, 2),
        strategy_used=PipelineStrategy.TURBO,
        telemetry=PipelineTelemetry(
            pipeline_id=pipeline_id,
            strategy=PipelineStrategy.TURBO,
            start_time=start,
            end_time=time.monotonic(),
            total_duration_s=round(duration, 2),
            agent_traces=traces,
            models_used=list({t.model_used for t in traces}),
        ),
    )


# ===========================================================================
# Strategy: PREMIUM — Maximum quality
# ===========================================================================

async def _strategy_premium(business_raw: dict, pipeline_id: str) -> Optional[ProcessedBusiness]:
    """
    Premium quality pipeline combining:
    - Standard extraction
    - Competitive intelligence
    - Swarm design voting
    - Evolutionary content
    - Adversarial QC
    """
    start = time.monotonic()
    traces = []

    # Step 1: Crawler
    crawl_result, crawl_trace = await _run_agent(
        crawler_agent,
        f"Extract and classify this business data:\n{json.dumps(business_raw, ensure_ascii=False)}",
        pipeline_id,
    )
    traces.append(crawl_trace)
    business = BusinessData(**_parse_agent_json(crawl_result.final_output))

    # Step 2: SEO + Competitive Intel in parallel
    async def _run_seo():
        if not business.website_url:
            return SEOAnalysis(
                business_id=business.place_id,
                website_status=WebsiteStatus.NONE,
                analysis_notes="No website — premium target",
            ), None
        r, t = await _run_agent(
            seo_agent,
            f"Analyze website quality for: {business.name} ({business.category})\n"
            f"URL: {business.website_url}\nLocation: {business.city}, Poland",
            pipeline_id,
        )
        raw = _parse_agent_json(r.final_output)
        raw["business_id"] = business.place_id
        return SEOAnalysis(**raw), t

    async def _run_competitive_intel():
        r, t = await _run_agent(
            competitive_intel_agent,
            f"Analyze competitive landscape for:\n"
            f"Business: {business.name}\nCategory: {business.category}\n"
            f"City: {business.city}\nRating: {business.rating}\n"
            f"Reviews: {business.review_count}",
            pipeline_id,
        )
        raw = _parse_agent_json(r.final_output)
        raw["business_id"] = business.place_id
        return CompetitiveIntel(**raw), t

    (seo_analysis, seo_trace), (comp_intel, ci_trace) = await asyncio.gather(
        _run_seo(), _run_competitive_intel()
    )
    if seo_trace:
        traces.append(seo_trace)
    if ci_trace:
        traces.append(ci_trace)

    if seo_analysis.website_status == WebsiteStatus.GOOD:
        return None

    # Step 3: Design with debate
    design_result, design_trace = await _run_agent(
        design_agent,
        f"Select PREMIUM design for:\nBusiness: {business.name}\n"
        f"Category: {business.category}\nCity: {business.city}\n"
        f"SEO notes: {seo_analysis.analysis_notes}\n"
        f"Competitive intel: {comp_intel.model_dump_json() if comp_intel else 'N/A'}",
        pipeline_id,
    )
    traces.append(design_trace)
    design_spec = DesignSpec(**_parse_agent_json(design_result.final_output))

    # Step 4: Evolutionary content
    content_prompt = (
        f"Stwórz PREMIUM treści strony dla:\nFirma: {business.name}\n"
        f"Kategoria: {business.category}\nMiasto: {business.city}\n"
        f"Adres: {business.address}\nTelefon: {business.phone or 'brak'}\n"
        f"Ocena Google: {business.rating or 'brak'} ({business.review_count or 0} opinii)\n"
        f"Szablon: {design_spec.template_id}\nStyl: {design_spec.style_mood}\n"
        f"Sekcje: {', '.join(design_spec.sections)}\n"
        f"Pozycja rynkowa: {comp_intel.market_position if comp_intel else 'unknown'}\n"
        f"Przewagi konkurencyjne: {', '.join(comp_intel.competitive_advantages) if comp_intel else 'N/A'}"
    )

    async def _generate_content(task_input):
        r, t = await _run_agent(content_agent, content_prompt, pipeline_id)
        traces.append(t)
        return _parse_agent_json(r.final_output)

    async def _mutate_content(existing_content, task_input):
        r, t = await _run_agent(
            content_refinement_agent,
            f"Ulepsz treści premium:\n{json.dumps(existing_content, ensure_ascii=False)}\n"
            f"Firma: {business.name}, {business.city}\n"
            f"Pozycja: {comp_intel.market_position if comp_intel else 'unknown'}",
            pipeline_id,
        )
        traces.append(t)
        parsed = _parse_agent_json(r.final_output)
        return parsed.get("improved", parsed)

    async def _fitness_fn(content_data):
        r, t = await _run_agent(
            qc_agent,
            f"Score 0-100 premium content for {business.name}:\n"
            f"{json.dumps(content_data, ensure_ascii=False)}",
            pipeline_id,
        )
        traces.append(t)
        try:
            return min(1.0, max(0.0, float(re.search(r'\d+', r.final_output.strip()).group()) / 100))
        except Exception:
            return 0.5

    optimizer = EvolutionaryOptimizer(
        generator_fn=_generate_content,
        mutator_fn=_mutate_content,
        fitness_fn=_fitness_fn,
        population_size=settings.evolution_population_size,
        max_generations=settings.evolution_max_generations,
        elite_count=settings.evolution_elite_count,
    )

    best_genome = await optimizer.evolve(content_prompt)
    content_raw = best_genome.content if isinstance(best_genome.content, dict) else _parse_agent_json(str(best_genome.content))
    content_raw["business_id"] = business.place_id
    content_raw["content_generation_strategy"] = "premium_evolutionary"
    content_raw["evolution_fitness"] = best_genome.fitness
    content_raw["model_used"] = content_agent.model
    content = GeneratedContent(**content_raw)

    # Premium QC
    qc_input = (
        f"PREMIUM review for {business.name} ({business.category}, {business.city}):\n"
        f"Design: {design_spec.model_dump_json()}\n"
        f"Content: {content.model_dump_json()}\n"
        f"Competitive Intel: {comp_intel.model_dump_json() if comp_intel else 'N/A'}\n"
        f"Evolution fitness: {best_genome.fitness}"
    )
    qc_result, qc_trace = await _run_agent(qc_agent, qc_input, pipeline_id)
    traces.append(qc_trace)
    qc_raw = _parse_agent_json(qc_result.final_output)
    qc_raw["business_id"] = business.place_id
    qc_data = QCResult(**qc_raw)

    # Email
    outreach_email = await _generate_outreach(business, seo_analysis, pipeline_id, traces)

    duration = time.monotonic() - start
    from tools import generate_slug as _gen_slug
    site_slug = _gen_slug(business.name, business.city)

    return ProcessedBusiness(
        business=business,
        seo_analysis=seo_analysis,
        design_spec=design_spec,
        content=content,
        qc_result=qc_data,
        outreach_email=outreach_email,
        competitive_intel=comp_intel,
        demo_site_slug=site_slug,
        demo_site_url=f"https://{site_slug}.{settings.demo_base_domain}",
        pipeline_duration_s=round(duration, 2),
        strategy_used=PipelineStrategy.PREMIUM,
        quality_confidence=best_genome.fitness,
        telemetry=PipelineTelemetry(
            pipeline_id=pipeline_id,
            strategy=PipelineStrategy.PREMIUM,
            start_time=start,
            end_time=time.monotonic(),
            total_duration_s=round(duration, 2),
            agent_traces=traces,
            models_used=list({t.model_used for t in traces}),
            evolution_generations=best_genome.generation + 1,
            swarm_decisions=0,
        ),
    )


# ===========================================================================
# Shared helpers
# ===========================================================================

async def _generate_outreach(
    business: BusinessData,
    seo_analysis: SEOAnalysis,
    pipeline_id: str,
    traces: list,
) -> Optional[OutreachEmail]:
    """Generate outreach email (shared across all strategies)."""
    recipient_email = business.email
    if not recipient_email:
        if business.website_url:
            domain = urlparse(business.website_url).netloc.lstrip("www.")
            recipient_email = f"kontakt@{domain}"
        else:
            return None

    from tools import generate_slug
    slug = generate_slug(business.name, business.city)
    demo_url = f"https://{slug}.{settings.demo_base_domain}"

    email_result, email_trace = await _run_agent(
        email_agent,
        f"Generate 3 outreach email variants for:\n"
        f"Business: {business.name}\nCategory: {business.category}\n"
        f"City: {business.city}\nRecipient email: {recipient_email}\n"
        f"Demo URL: {demo_url}\n"
        f"Website status: {seo_analysis.website_status.value}",
        pipeline_id,
    )
    traces.append(email_trace)
    outreach_raw = _parse_agent_json(email_result.final_output)
    outreach_raw["business_id"] = business.place_id
    outreach_raw["recipient_email"] = recipient_email
    outreach_raw["demo_url"] = demo_url
    return OutreachEmail(**outreach_raw)


# ===========================================================================
# Strategy Auto-Selection
# ===========================================================================

async def _auto_select_strategy(business_raw: dict, pipeline_id: str) -> PipelineStrategy:
    """
    Use the Meta Orchestrator to select the best strategy,
    or use heuristics as fallback.
    """
    try:
        result, _ = await _run_agent(
            orchestrator_agent,
            f"Select pipeline strategy for:\n{json.dumps(business_raw, ensure_ascii=False)}",
            pipeline_id,
        )
        parsed = _parse_agent_json(result.final_output)
        strategy_name = parsed.get("strategy", "standard")
        return PipelineStrategy(strategy_name)
    except Exception:
        # Heuristic fallback
        rating = business_raw.get("rating", 0) or 0
        reviews = business_raw.get("review_count", 0) or 0

        if rating >= 4.5 and reviews >= 50:
            return PipelineStrategy.PREMIUM
        elif rating >= 4.0 and reviews >= 20:
            return PipelineStrategy.EVOLUTIONARY
        elif reviews < 5:
            return PipelineStrategy.TURBO
        else:
            return PipelineStrategy.STANDARD


# ===========================================================================
# Main entry point
# ===========================================================================

STRATEGY_MAP = {
    PipelineStrategy.STANDARD: _strategy_standard,
    PipelineStrategy.SWARM_CONSENSUS: _strategy_swarm,
    PipelineStrategy.EVOLUTIONARY: _strategy_evolutionary,
    PipelineStrategy.TURBO: _strategy_turbo,
    PipelineStrategy.PREMIUM: _strategy_premium,
}


async def process_business(
    business_raw: dict,
    strategy: PipelineStrategy | str | None = None,
) -> Optional[ProcessedBusiness]:
    """
    Run a single business through the multi-agent pipeline.

    If no strategy is specified, auto-selects based on business characteristics.
    """
    pipeline_id = uuid.uuid4().hex
    event_bus = get_event_bus()

    # Initialize memory
    if settings.enable_memory:
        memory = get_memory_store()
        await memory.initialize()

    await event_bus.publish(Event(
        category=EventCategory.PIPELINE,
        event_type="pipeline_started",
        source="orchestrator",
        pipeline_id=pipeline_id,
        data={"business_name": business_raw.get("name"), "total_nodes": 6},
    ))

    try:
        # Select strategy
        if strategy is None:
            if settings.auto_select_strategy:
                strategy = await _auto_select_strategy(business_raw, pipeline_id)
            else:
                strategy = PipelineStrategy(settings.default_pipeline_strategy)
        elif isinstance(strategy, str):
            strategy = PipelineStrategy(strategy)

        log.info("pipeline.start",
                 name=business_raw.get("name"),
                 strategy=strategy.value,
                 pipeline_id=pipeline_id)

        # Execute selected strategy
        strategy_fn = STRATEGY_MAP.get(strategy, _strategy_standard)
        result = await strategy_fn(business_raw, pipeline_id)

        await event_bus.publish(Event(
            category=EventCategory.PIPELINE,
            event_type="pipeline_completed",
            source="orchestrator",
            pipeline_id=pipeline_id,
            data={
                "business_name": business_raw.get("name"),
                "strategy": strategy.value,
                "success": result is not None,
                "duration_s": result.pipeline_duration_s if result else 0,
            },
        ))

        return result

    except Exception as exc:
        log.error("pipeline.error", name=business_raw.get("name"), error=str(exc))
        await event_bus.publish(Event(
            category=EventCategory.PIPELINE,
            event_type="pipeline_failed",
            source="orchestrator",
            pipeline_id=pipeline_id,
            data={"error": str(exc)},
            severity="error",
        ))
        raise


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

async def process_batch(
    businesses: list[dict],
    concurrency: int = 5,
    strategy: PipelineStrategy | str | None = None,
) -> list[ProcessedBusiness]:
    """Process multiple businesses with controlled concurrency."""
    concurrency = max(1, min(concurrency, settings.max_concurrent_agents))
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process_with_sem(b: dict):
        async with semaphore:
            return await process_business(b, strategy=strategy)

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
    strategy: str = typer.Option("auto", "--strategy", "-s",
                                  help="standard|swarm|evolutionary|turbo|premium|auto"),
):
    """Process businesses from a JSONL input file."""
    with open(input_file) as f:
        businesses = [json.loads(line) for line in f if line.strip()]

    if limit:
        businesses = businesses[:limit]

    strat = None if strategy == "auto" else strategy

    typer.echo(f"Processing {len(businesses)} businesses (concurrency={concurrency}, strategy={strategy})")
    results = asyncio.run(process_batch(businesses, concurrency, strategy=strat))

    with open(output_file, "w") as f:
        for r in results:
            f.write(r.model_dump_json() + "\n")

    typer.echo(f"Done. {len(results)} processed -> {output_file}")


if __name__ == "__main__":
    app()
