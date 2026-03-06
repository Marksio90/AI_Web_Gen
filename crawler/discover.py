"""
Business Discovery CLI

Sources:
  1. Google Places API (New) — primary, 5K free calls/month per SKU
  2. OpenStreetMap Overpass API — free, unlimited, supplementary

Usage:
    python discover.py --city Warsaw --category restaurant --limit 500
    python discover.py --city "Kraków" --category beauty_salon --source osm
    python discover.py --cities-file cities.txt --all-categories
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from tenacity import retry, stop_after_attempt, wait_exponential

console = Console()
app = typer.Typer()

# ---------------------------------------------------------------------------
# Polish cities grid for systematic coverage
# ---------------------------------------------------------------------------
POLISH_CITIES = [
    ("Warsaw", 52.2297, 21.0122),
    ("Kraków", 50.0647, 19.9450),
    ("Łódź", 51.7592, 19.4560),
    ("Wrocław", 51.1079, 17.0385),
    ("Poznań", 52.4064, 16.9252),
    ("Gdańsk", 54.3520, 18.6466),
    ("Szczecin", 53.4285, 14.5528),
    ("Bydgoszcz", 53.1235, 18.0076),
    ("Lublin", 51.2465, 22.5684),
    ("Katowice", 50.2649, 19.0238),
    ("Białystok", 53.1325, 23.1688),
    ("Gdynia", 54.5189, 18.5305),
    ("Częstochowa", 50.8118, 19.1203),
    ("Radom", 51.4027, 21.1471),
    ("Sosnowiec", 50.2863, 19.1041),
    ("Toruń", 53.0138, 18.5981),
    ("Kielce", 50.8661, 20.6286),
    ("Rzeszów", 50.0412, 21.9991),
    ("Gliwice", 50.2945, 18.6714),
    ("Zabrze", 50.3249, 18.7857),
]

CATEGORY_GOOGLE_TYPES = {
    "restaurant": "restaurant",
    "beauty_salon": "beauty_salon",
    "dental_clinic": "dentist",
    "auto_repair": "car_repair",
    "law_office": "lawyer",
    "plumber": "plumber",
    "fitness": "gym",
    "pharmacy": "pharmacy",
    "hotel": "lodging",
    "bakery": "bakery",
    "florist": "florist",
    "accountant": "accounting",
    "physiotherapy": "physiotherapist",
    "optician": "optician",
}

CATEGORY_OSM_TAGS = {
    "restaurant": '[amenity=restaurant]',
    "beauty_salon": '[shop=hairdresser]',
    "dental_clinic": '[amenity=dentist]',
    "auto_repair": '[shop=car_repair]',
    "law_office": '[office=lawyer]',
    "plumber": '[trade=plumber]',
    "fitness": '[leisure=fitness_centre]',
    "pharmacy": '[amenity=pharmacy]',
    "hotel": '[tourism=hotel]',
    "bakery": '[shop=bakery]',
    "florist": '[shop=florist]',
    "accountant": '[office=accountant]',
}


# ---------------------------------------------------------------------------
# Google Places API (New)
# ---------------------------------------------------------------------------
class GooglePlacesCrawler:
    BASE_URL = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def search(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_m: int = 5000,
        max_results: int = 20,
        page_token: Optional[str] = None,
    ) -> dict:
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.websiteUri,"
                "places.formattedAddress,places.types,places.nationalPhoneNumber,"
                "places.rating,places.userRatingCount,places.regularOpeningHours,"
                "places.googleMapsUri,nextPageToken"
            ),
            "Content-Type": "application/json",
        }
        body = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_m,
                }
            },
            "maxResultCount": min(max_results, 20),
            "languageCode": "pl",
        }
        if page_token:
            body["pageToken"] = page_token

        resp = await self.client.post(self.BASE_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

    async def discover_city(
        self,
        city: str,
        lat: float,
        lng: float,
        category: str,
        limit: int = 100,
    ) -> list[dict]:
        google_type = CATEGORY_GOOGLE_TYPES.get(category, category)
        query = f"{google_type} {city} Poland"
        results = []
        page_token = None

        while len(results) < limit:
            data = await self.search(query, lat, lng, page_token=page_token)
            places = data.get("places", [])
            for place in places:
                results.append(self._normalize(place, city, category))

            page_token = data.get("nextPageToken")
            if not page_token or len(places) == 0:
                break
            await asyncio.sleep(2)  # Required delay between page requests

        return results[:limit]

    def _normalize(self, place: dict, city: str, category: str) -> dict:
        return {
            "place_id": place.get("id", ""),
            "name": place.get("displayName", {}).get("text", ""),
            "address": place.get("formattedAddress", ""),
            "city": city,
            "phone": place.get("nationalPhoneNumber"),
            "website_url": place.get("websiteUri"),
            "category": category,
            "google_maps_url": place.get("googleMapsUri"),
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount"),
            "source": "google_maps",
        }

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# OpenStreetMap Overpass API
# ---------------------------------------------------------------------------
class OSMCrawler:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    async def query(self, city: str, category: str, timeout: int = 30) -> list[dict]:
        osm_tag = CATEGORY_OSM_TAGS.get(category, f'[shop={category}]')
        overpass_query = f"""
[out:json][timeout:{timeout}];
area["name"="{city}"]["boundary"="administrative"]["admin_level"~"^[67]$"]->.city;
(
  node{osm_tag}(area.city);
  way{osm_tag}(area.city);
  relation{osm_tag}(area.city);
);
out center tags;
"""
        resp = await self.client.post(
            self.OVERPASS_URL,
            data={"data": overpass_query},
        )
        resp.raise_for_status()
        data = resp.json()
        return [self._normalize(el, city, category) for el in data.get("elements", [])]

    def _normalize(self, el: dict, city: str, category: str) -> dict:
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lng = el.get("lon") or el.get("center", {}).get("lon")
        return {
            "place_id": f"osm_{el['type']}_{el['id']}",
            "name": tags.get("name", ""),
            "address": self._build_address(tags),
            "city": city,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "email": tags.get("email") or tags.get("contact:email"),
            "website_url": tags.get("website") or tags.get("contact:website"),
            "category": category,
            "latitude": lat,
            "longitude": lng,
            "source": "osm",
        }

    def _build_address(self, tags: dict) -> str:
        parts = [
            tags.get("addr:street", ""),
            tags.get("addr:housenumber", ""),
            tags.get("addr:postcode", ""),
            tags.get("addr:city", ""),
        ]
        return " ".join(p for p in parts if p).strip()

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Website Quality Pre-filter (cheap HTTP check before PageSpeed)
# ---------------------------------------------------------------------------
async def quick_website_check(url: str) -> dict:
    """Rapid HTTP check to identify obviously broken/missing sites."""
    if not url:
        return {"status": "none"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp = await client.head(url, headers={"User-Agent": "Mozilla/5.0"})
            return {
                "status": "reachable" if resp.status_code < 400 else "error",
                "code": resp.status_code,
                "https": str(resp.url).startswith("https://"),
                "final_url": str(resp.url),
            }
    except Exception:
        return {"status": "unreachable"}


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------
@app.command()
def discover(
    city: str = typer.Option("Warsaw", "--city", "-c"),
    category: str = typer.Option("restaurant", "--category", "-t"),
    source: str = typer.Option("google", "--source", "-s", help="google | osm | both"),
    limit: int = typer.Option(100, "--limit", "-l"),
    output: str = typer.Option("businesses.jsonl", "--output", "-o"),
    api_key: str = typer.Option("", "--api-key", envvar="GOOGLE_MAPS_API_KEY"),
    filter_no_website: bool = typer.Option(True, "--filter-no-website/--all"),
):
    """Discover businesses in a Polish city by category."""
    import os
    api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")

    async def _run():
        results = []
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            if source in ("google", "both") and api_key:
                task = progress.add_task(f"Crawling Google Maps: {city} / {category}...", total=None)
                crawler = GooglePlacesCrawler(api_key)
                city_data = next((c for c in POLISH_CITIES if c[0].lower() == city.lower()), None)
                if city_data:
                    _, lat, lng = city_data
                else:
                    lat, lng = 52.2297, 21.0122  # default Warsaw
                places = await crawler.discover_city(city, lat, lng, category, limit)
                await crawler.close()
                results.extend(places)
                progress.update(task, description=f"Google Maps: {len(places)} found")

            if source in ("osm", "both"):
                task = progress.add_task(f"Crawling OpenStreetMap: {city} / {category}...", total=None)
                osm = OSMCrawler()
                osm_places = await osm.query(city, category)
                await osm.close()
                results.extend(osm_places)
                progress.update(task, description=f"OSM: {len(osm_places)} found")

        # Deduplicate by name + city
        seen = set()
        unique = []
        for r in results:
            key = (r["name"].lower().strip(), r["city"].lower())
            if key not in seen and r["name"]:
                seen.add(key)
                unique.append(r)

        # Optional: filter to only businesses without websites
        if filter_no_website:
            unique = [b for b in unique if not b.get("website_url")]
            console.print(f"[yellow]After filtering (no website): {len(unique)} businesses[/yellow]")

        # Write output
        with open(output, "w", encoding="utf-8") as f:
            for b in unique:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")

        console.print(f"[green]Done! {len(unique)} businesses saved to {output}[/green]")

    asyncio.run(_run())


@app.command()
def scan_all_cities(
    category: str = typer.Option("restaurant", "--category", "-t"),
    source: str = typer.Option("both", "--source", "-s"),
    limit_per_city: int = typer.Option(200, "--limit-per-city"),
    output_dir: str = typer.Option("data/", "--output-dir"),
    api_key: str = typer.Option("", "--api-key", envvar="GOOGLE_MAPS_API_KEY"),
):
    """Scan all major Polish cities for a business category."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for city, lat, lng in POLISH_CITIES:
        out_file = Path(output_dir) / f"{city.lower()}_{category}.jsonl"
        console.print(f"[blue]Processing {city}...[/blue]")
        # Call discover for each city (simplified — production should batch)
        import subprocess, sys
        subprocess.run([
            sys.executable, __file__, "discover",
            "--city", city, "--category", category,
            "--source", source, "--limit", str(limit_per_city),
            "--output", str(out_file),
            "--api-key", api_key,
        ])


if __name__ == "__main__":
    app()
