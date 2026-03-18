"""
Shared Pydantic models for inter-agent communication.

Extended with advanced pipeline telemetry, swarm decision data,
competitive intelligence, and multi-algorithm metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WebsiteStatus(str, Enum):
    NONE = "none"          # No website at all
    POOR = "poor"          # Website exists but scores badly
    GOOD = "good"          # Website is fine — skip
    UNKNOWN = "unknown"    # Could not determine


class BusinessCategory(str, Enum):
    RESTAURANT = "restaurant"
    BEAUTY_SALON = "beauty_salon"
    DENTAL_CLINIC = "dental_clinic"
    AUTO_REPAIR = "auto_repair"
    LAW_OFFICE = "law_office"
    PLUMBER = "plumber"
    FITNESS = "fitness"
    PHARMACY = "pharmacy"
    HOTEL = "hotel"
    BAKERY = "bakery"
    FLORIST = "florist"
    ACCOUNTANT = "accountant"
    PHYSIOTHERAPY = "physiotherapy"
    OPTICIAN = "optician"
    VETERINARY = "veterinary"
    REAL_ESTATE = "real_estate"
    EDUCATION = "education"
    IT_SERVICES = "it_services"
    CONSTRUCTION = "construction"
    CLEANING = "cleaning"
    OTHER = "other"


class PipelineStrategy(str, Enum):
    """Pipeline execution strategy selection."""
    STANDARD = "standard"            # Linear 6-agent pipeline
    SWARM_CONSENSUS = "swarm"        # Swarm intelligence voting
    EVOLUTIONARY = "evolutionary"    # Genetic algorithm optimization
    DEBATE = "debate"                # Adversarial debate protocol
    TURBO = "turbo"                  # Parallel fast-path with nano models
    PREMIUM = "premium"              # Maximum quality, all premium models


# ---------------------------------------------------------------------------
# Business & SEO Models
# ---------------------------------------------------------------------------

class BusinessData(BaseModel):
    """Raw business data from crawler."""
    place_id: str
    name: str
    address: str
    city: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    category: BusinessCategory = BusinessCategory.OTHER
    google_maps_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    opening_hours: Optional[dict] = None
    source: str = "google_maps"
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Competitive intelligence
    competitor_count: Optional[int] = None
    market_saturation: Optional[float] = None  # 0-1, how saturated the local market is
    social_media: Optional[dict] = None  # {facebook, instagram, google_business}


class SEOAnalysis(BaseModel):
    """Output of SEO Analysis Agent."""
    business_id: str
    website_status: WebsiteStatus
    performance_score: Optional[int] = None
    seo_score: Optional[int] = None
    accessibility_score: Optional[int] = None
    is_mobile_friendly: Optional[bool] = None
    has_https: Optional[bool] = None
    has_viewport_meta: Optional[bool] = None
    page_load_time_ms: Optional[int] = None
    keyword_opportunities: list[str] = []
    local_competitors: list[str] = []
    analysis_notes: str = ""
    # Advanced SEO metrics
    domain_authority: Optional[float] = None
    backlink_count: Optional[int] = None
    technical_issues: list[str] = []
    content_gaps: list[str] = []
    local_seo_score: Optional[int] = None


class CompetitiveIntel(BaseModel):
    """Competitive intelligence data for a business's local market."""
    business_id: str
    total_competitors: int = 0
    competitors_with_websites: int = 0
    avg_competitor_rating: Optional[float] = None
    avg_competitor_review_count: Optional[int] = None
    market_position: str = "unknown"  # leader, challenger, follower, niche
    competitive_advantages: list[str] = []
    improvement_opportunities: list[str] = []
    price_positioning: str = "unknown"  # premium, mid-range, budget


# ---------------------------------------------------------------------------
# Design & Content Models
# ---------------------------------------------------------------------------

class DesignSpec(BaseModel):
    """Output of Design Agent — drives template selection."""
    template_id: str          # e.g. "restaurant-modern", "dental-clean"
    primary_color: str        # hex, e.g. "#2D6A4F"
    secondary_color: str      # hex
    accent_color: str         # hex
    font_heading: str         # Google Font name
    font_body: str
    sections: list[str]       # ordered list of section component IDs
    style_mood: str           # "professional", "warm", "modern", "elegant"
    image_style: str          # "photography", "illustration", "minimal"
    # Advanced design tokens
    border_radius: str = "8px"
    shadow_style: str = "subtle"  # none, subtle, dramatic
    animation_style: str = "smooth"  # none, smooth, playful
    layout_density: str = "balanced"  # compact, balanced, spacious


class GeneratedContent(BaseModel):
    """Output of Content Generation Agent."""
    business_id: str
    hero_headline: str
    hero_subheadline: str
    hero_cta: str
    about_text: str           # 2-3 paragraphs
    services: list[dict]      # [{name, description, price?}]
    testimonials: list[dict]  # [{author, role, text, rating}]
    contact_section: dict
    meta_title: str           # max 60 chars
    meta_description: str     # max 160 chars
    keywords: list[str]
    page_title: str
    footer_text: str
    language: str = "pl"
    # Advanced content metadata
    content_generation_strategy: str = "standard"
    evolution_generation: Optional[int] = None
    evolution_fitness: Optional[float] = None
    swarm_confidence: Optional[float] = None
    model_used: str = ""


class QCResult(BaseModel):
    """Output of Quality Control Agent."""
    business_id: str
    approved: bool
    content_score: int        # 0-100
    seo_score: int            # 0-100
    brand_score: int          # 0-100
    overall_score: int        # 0-100
    issues: list[str] = []
    suggestions: list[str] = []
    iteration: int = 1
    # Advanced QC data
    ensemble_scores: Optional[dict] = None  # scores from multiple QC algorithms
    consensus_confidence: Optional[float] = None
    auto_fix_applied: list[str] = []  # automatic fixes applied


# ---------------------------------------------------------------------------
# Email Models
# ---------------------------------------------------------------------------

class EmailVariant(BaseModel):
    """Single outreach email variant."""
    subject: str
    body_text: str            # plain text
    body_html: str            # HTML with inline styles
    variant_label: str        # "A", "B", "C"
    predicted_open_rate: Optional[float] = None
    predicted_response_rate: Optional[float] = None


class OutreachEmail(BaseModel):
    """Output of Email Outreach Agent."""
    business_id: str
    recipient_email: str
    recipient_name: Optional[str] = None
    demo_url: str
    variants: list[EmailVariant]  # 2-3 A/B variants
    unsubscribe_token: str
    optimal_send_time: Optional[str] = None  # Predicted best time to send


# ---------------------------------------------------------------------------
# Pipeline Telemetry Models
# ---------------------------------------------------------------------------

class AgentExecutionTrace(BaseModel):
    """Execution trace for a single agent in the pipeline."""
    agent_id: str
    agent_name: str
    model_used: str
    start_time: float
    end_time: float
    duration_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    success: bool = True
    error: Optional[str] = None


class PipelineTelemetry(BaseModel):
    """Complete telemetry for a pipeline execution."""
    pipeline_id: str
    strategy: PipelineStrategy = PipelineStrategy.STANDARD
    start_time: float
    end_time: float
    total_duration_s: float
    agent_traces: list[AgentExecutionTrace] = []
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    models_used: list[str] = []
    dag_execution_waves: int = 0
    parallel_agents_max: int = 0
    swarm_decisions: int = 0
    evolution_generations: int = 0
    checkpoints_created: int = 0
    memory_episodes_recorded: int = 0


# ---------------------------------------------------------------------------
# Top-Level Output
# ---------------------------------------------------------------------------

class ProcessedBusiness(BaseModel):
    """Final output of the full pipeline for one business."""
    business: BusinessData
    seo_analysis: SEOAnalysis
    design_spec: DesignSpec
    content: GeneratedContent
    qc_result: QCResult
    outreach_email: Optional[OutreachEmail] = None
    competitive_intel: Optional[CompetitiveIntel] = None
    demo_site_url: Optional[str] = None
    demo_site_slug: str = ""
    pipeline_duration_s: Optional[float] = None
    total_cost_usd: Optional[float] = None
    # Advanced pipeline metadata
    strategy_used: PipelineStrategy = PipelineStrategy.STANDARD
    telemetry: Optional[PipelineTelemetry] = None
    quality_confidence: Optional[float] = None  # 0-1, how confident the system is
