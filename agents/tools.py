"""Tool functions available to agents (decorated for OpenAI Agents SDK)."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx
from agents import function_tool

from config import settings


def _is_safe_url(url: str) -> bool:
    """Reject URLs pointing to internal/cloud metadata addresses (SSRF protection)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        # Block well-known internal hostnames
        blocked = {"localhost", "metadata.google.internal", "metadata.gce.internal"}
        if hostname in blocked:
            return False
        # Resolve and check for private IPs
        for info in socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        return True
    except Exception:
        return False


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
    }
    # Fallback: use a generic professional template for unknown categories
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
    import re
    import unicodedata

    text = f"{business_name}-{city}".lower()
    # Normalize Polish diacritics
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l",
        "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    }
    for pl, en in replacements.items():
        text = text.replace(pl, en)
    text = re.sub(r"[^a-z0-9-]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    # Ensure uniqueness with short hash
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
    }
    query = category_queries.get(category, "small business professional")
    # Pexels API — requires PEXELS_API_KEY in env (free tier: 200 requests/hour)
    import os
    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        # Return placeholder structure when key not set
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
