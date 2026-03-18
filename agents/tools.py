"""
Tool functions available to agents (decorated for OpenAI Agents SDK).

Extended with competitive intelligence, technology stack detection,
and advanced market analysis tools.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import httpx
from agents import function_tool

from config import settings


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def _is_safe_url(url: str) -> bool:
    """Reject URLs pointing to internal/cloud metadata addresses (SSRF protection)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        blocked = {"localhost", "metadata.google.internal", "metadata.gce.internal"}
        if hostname in blocked:
            return False
        for info in socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core Tools (Original)
# ---------------------------------------------------------------------------

@function_tool
async def check_website_exists(url: str) -> dict:
    """Check if a URL is reachable and return basic HTTP info."""
    if not url:
        return {"reachable": False, "status_code": None, "redirect_url": None}
    if not _is_safe_url(url):
        return {"reachable": False, "error": "URL blocked by security policy"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.head(url, headers={"User-Agent": "Mozilla/5.0"})
            return {
                "reachable": resp.status_code < 400,
                "status_code": resp.status_code,
                "final_url": str(resp.url),
                "has_https": str(resp.url).startswith("https://"),
            }
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}


@function_tool
async def get_pagespeed_score(url: str) -> dict:
    """Fetch PageSpeed Insights scores for mobile and desktop."""
    if not url:
        return {"error": "No URL provided"}
    if not _is_safe_url(url):
        return {"error": "URL blocked by security policy"}
    api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    results = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for strategy in ("mobile", "desktop"):
            params = {
                "url": url,
                "strategy": strategy,
                "key": settings.pagespeed_api_key,
                "fields": "lighthouseResult.categories,lighthouseResult.audits.viewport",
            }
            try:
                resp = await client.get(api_url, params=params)
                data = resp.json()
                cats = data.get("lighthouseResult", {}).get("categories", {})
                viewport = (
                    data.get("lighthouseResult", {})
                    .get("audits", {})
                    .get("viewport", {})
                    .get("score", 0)
                )
                results[strategy] = {
                    "performance": int((cats.get("performance", {}).get("score", 0) or 0) * 100),
                    "seo": int((cats.get("seo", {}).get("score", 0) or 0) * 100),
                    "accessibility": int((cats.get("accessibility", {}).get("score", 0) or 0) * 100),
                    "has_viewport": bool(viewport),
                }
            except Exception as exc:
                results[strategy] = {"error": str(exc)}
    return results


@function_tool
def get_industry_template(category: str) -> dict:
    """Return available template IDs and section options for a business category."""
    templates = {
        "restaurant": {
            "templates": ["restaurant-modern", "restaurant-warm", "restaurant-elegant"],
            "default_sections": ["hero", "menu-preview", "about", "gallery", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#8B1A1A", "secondary": "#F5E6D3", "accent": "#D4A853"},
                {"primary": "#2D4A2D", "secondary": "#F0F7EE", "accent": "#8FAF6F"},
            ],
        },
        "beauty_salon": {
            "templates": ["beauty-minimal", "beauty-elegant", "beauty-vibrant"],
            "default_sections": ["hero", "services", "about", "team", "booking-cta", "gallery", "contact"],
            "color_palettes": [
                {"primary": "#8B4B7E", "secondary": "#FDF0F8", "accent": "#E8A0CC"},
                {"primary": "#2C2C2C", "secondary": "#F8F4EF", "accent": "#C9A96E"},
            ],
        },
        "dental_clinic": {
            "templates": ["dental-clean", "dental-professional", "dental-modern"],
            "default_sections": ["hero", "services", "about", "team", "technology", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#1B6CA8", "secondary": "#F0F8FF", "accent": "#4ECDC4"},
                {"primary": "#2E7D32", "secondary": "#F1F8F1", "accent": "#81C784"},
            ],
        },
        "auto_repair": {
            "templates": ["auto-bold", "auto-industrial", "auto-modern"],
            "default_sections": ["hero", "services", "about", "pricing", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#1A1A2E", "secondary": "#F5F5F5", "accent": "#E94560"},
                {"primary": "#B8360A", "secondary": "#FFF8F5", "accent": "#F5A623"},
            ],
        },
        "law_office": {
            "templates": ["law-prestigious", "law-modern", "law-minimal"],
            "default_sections": ["hero", "practice-areas", "about", "team", "process", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#1C2B3A", "secondary": "#F8F6F2", "accent": "#C9A84C"},
                {"primary": "#2C3E50", "secondary": "#FAFAFA", "accent": "#3498DB"},
            ],
        },
        "plumber": {
            "templates": ["plumber-trusted", "plumber-modern"],
            "default_sections": ["hero", "services", "about", "emergency-cta", "pricing", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#0D47A1", "secondary": "#E3F2FD", "accent": "#FF6F00"},
                {"primary": "#1B5E20", "secondary": "#F1F8E9", "accent": "#FF8F00"},
            ],
        },
        "fitness": {
            "templates": ["fitness-energetic", "fitness-modern", "fitness-minimal"],
            "default_sections": ["hero", "classes", "about", "team", "schedule", "pricing", "contact"],
            "color_palettes": [
                {"primary": "#E53935", "secondary": "#FFF8F8", "accent": "#FFA000"},
                {"primary": "#1565C0", "secondary": "#E8F4FD", "accent": "#00ACC1"},
            ],
        },
        "pharmacy": {
            "templates": ["pharmacy-clean", "pharmacy-modern"],
            "default_sections": ["hero", "services", "about", "products", "team", "contact"],
            "color_palettes": [
                {"primary": "#00695C", "secondary": "#E0F2F1", "accent": "#4DB6AC"},
                {"primary": "#1565C0", "secondary": "#E3F2FD", "accent": "#42A5F5"},
            ],
        },
        "hotel": {
            "templates": ["hotel-luxury", "hotel-modern", "hotel-cozy"],
            "default_sections": ["hero", "rooms", "about", "amenities", "gallery", "testimonials", "booking-cta", "contact"],
            "color_palettes": [
                {"primary": "#1A237E", "secondary": "#F5F5F0", "accent": "#C9A84C"},
                {"primary": "#3E2723", "secondary": "#FFF8E1", "accent": "#FF8F00"},
            ],
        },
        "bakery": {
            "templates": ["bakery-warm", "bakery-artisan"],
            "default_sections": ["hero", "products", "about", "gallery", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#5D4037", "secondary": "#FFF8E1", "accent": "#F9A825"},
                {"primary": "#BF360C", "secondary": "#FBE9E7", "accent": "#FF8A65"},
            ],
        },
        "florist": {
            "templates": ["florist-elegant", "florist-fresh"],
            "default_sections": ["hero", "services", "gallery", "about", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#2E7D32", "secondary": "#F1F8E9", "accent": "#E91E63"},
                {"primary": "#880E4F", "secondary": "#FCE4EC", "accent": "#4CAF50"},
            ],
        },
        "accountant": {
            "templates": ["accountant-professional", "accountant-modern"],
            "default_sections": ["hero", "services", "about", "process", "testimonials", "faq", "contact"],
            "color_palettes": [
                {"primary": "#263238", "secondary": "#ECEFF1", "accent": "#00897B"},
                {"primary": "#1A237E", "secondary": "#E8EAF6", "accent": "#3F51B5"},
            ],
        },
        "physiotherapy": {
            "templates": ["physio-wellness", "physio-modern"],
            "default_sections": ["hero", "services", "about", "team", "testimonials", "booking-cta", "contact"],
            "color_palettes": [
                {"primary": "#00695C", "secondary": "#E0F2F1", "accent": "#26A69A"},
                {"primary": "#1565C0", "secondary": "#E3F2FD", "accent": "#29B6F6"},
            ],
        },
        "optician": {
            "templates": ["optician-modern", "optician-premium"],
            "default_sections": ["hero", "services", "brands", "about", "team", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#37474F", "secondary": "#ECEFF1", "accent": "#00ACC1"},
                {"primary": "#1B5E20", "secondary": "#E8F5E9", "accent": "#66BB6A"},
            ],
        },
        # New categories
        "veterinary": {
            "templates": ["vet-friendly", "vet-modern"],
            "default_sections": ["hero", "services", "about", "team", "testimonials", "emergency-cta", "contact"],
            "color_palettes": [
                {"primary": "#2E7D32", "secondary": "#F1F8E9", "accent": "#FF8F00"},
                {"primary": "#00695C", "secondary": "#E0F2F1", "accent": "#FFA000"},
            ],
        },
        "real_estate": {
            "templates": ["realestate-luxury", "realestate-modern"],
            "default_sections": ["hero", "listings", "about", "services", "team", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#1A237E", "secondary": "#F5F5F0", "accent": "#C9A84C"},
                {"primary": "#263238", "secondary": "#FAFAFA", "accent": "#26C6DA"},
            ],
        },
        "education": {
            "templates": ["education-friendly", "education-modern"],
            "default_sections": ["hero", "courses", "about", "team", "testimonials", "faq", "contact"],
            "color_palettes": [
                {"primary": "#1565C0", "secondary": "#E3F2FD", "accent": "#FFA000"},
                {"primary": "#6A1B9A", "secondary": "#F3E5F5", "accent": "#7C4DFF"},
            ],
        },
        "it_services": {
            "templates": ["it-futuristic", "it-clean"],
            "default_sections": ["hero", "services", "about", "technology", "portfolio", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#0D1B2A", "secondary": "#F0F4F8", "accent": "#00E5FF"},
                {"primary": "#1A237E", "secondary": "#E8EAF6", "accent": "#69F0AE"},
            ],
        },
        "construction": {
            "templates": ["construction-bold", "construction-modern"],
            "default_sections": ["hero", "services", "about", "portfolio", "process", "testimonials", "contact"],
            "color_palettes": [
                {"primary": "#E65100", "secondary": "#FFF3E0", "accent": "#FFC107"},
                {"primary": "#37474F", "secondary": "#ECEFF1", "accent": "#FF6D00"},
            ],
        },
        "cleaning": {
            "templates": ["cleaning-fresh", "cleaning-modern"],
            "default_sections": ["hero", "services", "about", "pricing", "testimonials", "booking-cta", "contact"],
            "color_palettes": [
                {"primary": "#00838F", "secondary": "#E0F7FA", "accent": "#4DB6AC"},
                {"primary": "#1565C0", "secondary": "#E3F2FD", "accent": "#26C6DA"},
            ],
        },
    }
    default_template = {
        "templates": ["generic-professional", "generic-modern"],
        "default_sections": ["hero", "services", "about", "testimonials", "contact"],
        "color_palettes": [
            {"primary": "#1A1A2E", "secondary": "#F5F5F5", "accent": "#6366F1"},
            {"primary": "#2D3436", "secondary": "#FAFAFA", "accent": "#0984E3"},
        ],
    }
    return templates.get(category, default_template)


@function_tool
def generate_slug(business_name: str, city: str) -> str:
    """Generate a URL-safe slug for a business demo site subdomain."""
    text = f"{business_name}-{city}".lower()
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l",
        "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    }
    for pl, en in replacements.items():
        text = text.replace(pl, en)
    text = re.sub(r"[^a-z0-9-]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    hash_suffix = hashlib.sha256(f"{business_name}{city}".encode()).hexdigest()[:6]
    return f"{text[:40]}-{hash_suffix}"


@function_tool
async def fetch_stock_images(category: str, count: int = 5) -> list[dict]:
    """Fetch free stock images from Pexels for a business category."""
    category_queries = {
        "restaurant": "restaurant interior food polish",
        "beauty_salon": "beauty salon spa interior",
        "dental_clinic": "dental clinic modern clean",
        "auto_repair": "auto repair garage mechanic",
        "law_office": "law office professional interior",
        "plumber": "plumbing professional tools",
        "fitness": "gym fitness workout interior",
        "pharmacy": "pharmacy drugstore modern interior",
        "hotel": "hotel room luxury interior",
        "bakery": "bakery bread pastry artisan",
        "florist": "flower shop florist bouquet",
        "accountant": "office accounting professional business",
        "physiotherapy": "physiotherapy clinic rehabilitation",
        "optician": "optician eyeglasses shop modern",
        "veterinary": "veterinary clinic animal care",
        "real_estate": "real estate modern interior house",
        "education": "education school classroom modern",
        "it_services": "technology office modern workspace",
        "construction": "construction building professional",
        "cleaning": "cleaning service professional home",
    }
    query = category_queries.get(category, "small business professional")
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        return [{"url": f"https://picsum.photos/800/600?random={i}", "alt": query} for i in range(count)]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": count, "orientation": "landscape"},
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        return [
            {"url": p.get("src", {}).get("large", ""), "alt": p.get("alt", ""), "photographer": p.get("photographer", "")}
            for p in photos if p.get("src")
        ]


# ---------------------------------------------------------------------------
# Competitive Intelligence Tools (New)
# ---------------------------------------------------------------------------

@function_tool
async def analyze_local_competition(
    city: str,
    category: str,
    business_name: str = "",
) -> dict:
    """
    Analyze local competition for a business category in a Polish city.
    Uses Google Maps text search to find competitors.
    """
    api_key = settings.google_maps_api_key
    if not api_key:
        return {
            "competitors_found": 0,
            "note": "Google Maps API key not configured — returning estimates",
            "estimated_competitors": _estimate_competition(city, category),
            "market_saturation": _estimate_saturation(category),
        }

    query = f"{category.replace('_', ' ')} {city} Poland"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key, "language": "pl"},
            )
            data = resp.json()
            results = data.get("results", [])

            competitors = []
            ratings = []
            review_counts = []

            for place in results[:20]:
                name = place.get("name", "")
                if name.lower() == business_name.lower():
                    continue  # Skip the business itself

                rating = place.get("rating", 0)
                reviews = place.get("user_ratings_total", 0)

                competitors.append({
                    "name": name,
                    "rating": rating,
                    "review_count": reviews,
                    "address": place.get("formatted_address", ""),
                    "types": place.get("types", []),
                })

                if rating:
                    ratings.append(rating)
                if reviews:
                    review_counts.append(reviews)

            return {
                "competitors_found": len(competitors),
                "competitors": competitors[:10],
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "avg_review_count": round(sum(review_counts) / len(review_counts)) if review_counts else None,
                "max_rating": max(ratings) if ratings else None,
                "max_reviews": max(review_counts) if review_counts else None,
                "market_saturation": min(1.0, len(competitors) / 20),
            }
    except Exception as exc:
        return {"error": str(exc), "competitors_found": 0}


@function_tool
async def scrape_competitor_content(url: str) -> dict:
    """
    Scrape basic content structure from a competitor's website.
    Used for competitive analysis — what sections/features do they have?
    """
    if not url or not _is_safe_url(url):
        return {"error": "URL not provided or blocked"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code >= 400:
                return {"error": f"HTTP {resp.status_code}"}

            html = resp.text
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Extract key content indicators
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag:
                meta_desc = meta_tag.get("content", "")

            # Count key sections
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])[:20]]
            has_contact_form = bool(soup.find("form"))
            has_phone = bool(re.search(r'\+?48[\s-]?\d{2,3}[\s-]?\d{3}[\s-]?\d{2,3}', html))
            has_map = bool(soup.find("iframe", src=re.compile(r"google.*maps|openstreetmap")))
            has_gallery = len(soup.find_all("img")) > 10
            has_pricing = bool(re.search(r'cen[aiy]|price|koszt|PLN|zł', html, re.I))
            has_testimonials = bool(re.search(r'opini[aei]|recenzj|testimonial|review', html, re.I))

            return {
                "title": title[:100],
                "meta_description": meta_desc[:200],
                "headings": headings,
                "has_contact_form": has_contact_form,
                "has_phone_number": has_phone,
                "has_map": has_map,
                "has_gallery": has_gallery,
                "has_pricing": has_pricing,
                "has_testimonials": has_testimonials,
                "total_images": len(soup.find_all("img")),
                "total_links": len(soup.find_all("a")),
            }
    except Exception as exc:
        return {"error": str(exc)}


@function_tool
async def get_technology_stack(url: str) -> dict:
    """
    Detect the technology stack of a website.
    Useful for understanding competitor capabilities.
    """
    if not url or not _is_safe_url(url):
        return {"error": "URL not provided or blocked"}

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

            headers = dict(resp.headers)
            html = resp.text.lower()

            technologies = []

            # Server detection
            server = headers.get("server", "").lower()
            if "nginx" in server:
                technologies.append("Nginx")
            elif "apache" in server:
                technologies.append("Apache")
            elif "cloudflare" in server:
                technologies.append("Cloudflare")

            # CMS detection
            if "wp-content" in html or "wordpress" in html:
                technologies.append("WordPress")
            elif "joomla" in html:
                technologies.append("Joomla")
            elif "drupal" in html:
                technologies.append("Drupal")
            elif "wix.com" in html:
                technologies.append("Wix")
            elif "squarespace" in html:
                technologies.append("Squarespace")
            elif "shopify" in html:
                technologies.append("Shopify")
            elif "webflow" in html:
                technologies.append("Webflow")

            # JS frameworks
            if "react" in html or "_next" in html or "next.js" in html:
                technologies.append("React/Next.js")
            elif "vue" in html or "nuxt" in html:
                technologies.append("Vue/Nuxt")
            elif "angular" in html:
                technologies.append("Angular")

            # Analytics
            if "google-analytics" in html or "gtag" in html or "ga(" in html:
                technologies.append("Google Analytics")
            if "facebook.com/tr" in html or "fbq(" in html:
                technologies.append("Facebook Pixel")

            # SSL
            is_https = str(resp.url).startswith("https")

            return {
                "technologies": technologies,
                "is_https": is_https,
                "server": headers.get("server", "unknown"),
                "content_type": headers.get("content-type", ""),
                "has_modern_framework": any(
                    t in technologies for t in ["React/Next.js", "Vue/Nuxt", "Angular", "Webflow"]
                ),
                "has_cms": any(
                    t in technologies for t in ["WordPress", "Joomla", "Drupal", "Wix", "Squarespace", "Shopify"]
                ),
            }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Competition estimation helpers (when API key not available)
# ---------------------------------------------------------------------------

def _estimate_competition(city: str, category: str) -> int:
    """Rough estimate of competitors based on city size."""
    city_sizes = {
        "Warsaw": 1800000, "Kraków": 780000, "Wrocław": 640000,
        "Gdańsk": 470000, "Poznań": 540000, "Łódź": 680000,
        "Katowice": 290000, "Lublin": 340000, "Szczecin": 400000,
        "Bydgoszcz": 340000, "Białystok": 300000, "Gdynia": 250000,
        "Częstochowa": 220000, "Radom": 210000, "Sosnowiec": 200000,
        "Toruń": 200000, "Kielce": 195000, "Rzeszów": 195000,
        "Gliwice": 180000, "Olsztyn": 170000,
    }
    pop = city_sizes.get(city, 200000)
    # Rough per-capita rates per category
    rates = {
        "restaurant": 0.0005, "beauty_salon": 0.0003, "dental_clinic": 0.0002,
        "auto_repair": 0.0002, "law_office": 0.00015, "plumber": 0.00015,
        "fitness": 0.0001, "pharmacy": 0.00015, "hotel": 0.00008,
        "bakery": 0.0002, "florist": 0.0001, "accountant": 0.0002,
        "physiotherapy": 0.0001, "optician": 0.00008, "veterinary": 0.0001,
        "real_estate": 0.00015, "education": 0.0001, "it_services": 0.0001,
        "construction": 0.0002, "cleaning": 0.0001,
    }
    rate = rates.get(category, 0.00015)
    return max(5, int(pop * rate))


def _estimate_saturation(category: str) -> float:
    """Rough market saturation estimate."""
    saturations = {
        "restaurant": 0.8, "beauty_salon": 0.7, "dental_clinic": 0.5,
        "auto_repair": 0.6, "law_office": 0.4, "plumber": 0.5,
        "fitness": 0.6, "pharmacy": 0.7, "hotel": 0.5,
        "bakery": 0.6, "florist": 0.4, "accountant": 0.5,
        "physiotherapy": 0.4, "optician": 0.3, "veterinary": 0.4,
        "real_estate": 0.6, "education": 0.4, "it_services": 0.5,
        "construction": 0.5, "cleaning": 0.4,
    }
    return saturations.get(category, 0.5)
