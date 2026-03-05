"""Shared Pydantic models for inter-agent communication."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


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
    OTHER = "other"


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
    discovered_at: datetime = datetime.utcnow()


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


class EmailVariant(BaseModel):
    """Single outreach email variant."""
    subject: str
    body_text: str            # plain text
    body_html: str            # HTML with inline styles
    variant_label: str        # "A", "B", "C"


class OutreachEmail(BaseModel):
    """Output of Email Outreach Agent."""
    business_id: str
    recipient_email: str
    recipient_name: Optional[str] = None
    demo_url: str
    variants: list[EmailVariant]  # 2-3 A/B variants
    unsubscribe_token: str


class ProcessedBusiness(BaseModel):
    """Final output of the full pipeline for one business."""
    business: BusinessData
    seo_analysis: SEOAnalysis
    design_spec: DesignSpec
    content: GeneratedContent
    qc_result: QCResult
    outreach_email: Optional[OutreachEmail] = None
    demo_site_url: Optional[str] = None
    demo_site_slug: str = ""
    pipeline_duration_s: Optional[float] = None
    total_cost_usd: Optional[float] = None
