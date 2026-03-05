"""
OSMScout — Free-tier HVAC company discovery via OpenStreetMap Overpass API.

No API key required. Queries OSM for businesses tagged as HVAC-related.
Falls back to YPScraper when fewer than 5 results found (see orchestrator).
"""
import asyncio
import logging
import httpx
from typing import Callable, Optional

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Full state name required by Overpass area queries
STATE_NAME_MAP = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# OSM tags that indicate HVAC/related businesses
HVAC_TAG_FILTERS = [
    '["shop"="hvac"]',
    '["craft"="hvac"]',
    '["craft"="heating"]',
    '["craft"="plumber"]',
    '["shop"="plumber"]',
]


def _osm_element_to_company(element: dict, city: str, state: str) -> Optional[dict]:
    """Map a single OSM element to our Company dict structure. Returns None if unusable."""
    tags = element.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    # Build address from OSM addr tags
    street = tags.get("addr:street", "")
    housenumber = tags.get("addr:housenumber", "")
    osm_city = tags.get("addr:city", city)
    osm_state = tags.get("addr:state", state)
    address_parts = [p for p in [housenumber, street, osm_city, osm_state] if p]
    address = ", ".join(address_parts) if address_parts else f"{city}, {state}"

    return {
        "place_id": f"osm_{element['type']}_{element['id']}",
        "name": name,
        "address": address,
        "city": osm_city or city,
        "state": osm_state or state,
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "website": tags.get("website") or tags.get("contact:website"),
        "google_rating": None,
        "google_review_count": 0,
        "category": "HVAC",
        "raw_google_data": {"source": "openstreetmap", "osm_id": element["id"]},
    }


def _build_overpass_query(city: str, state: str) -> str:
    """Build Overpass QL query for HVAC businesses in a given city/state."""
    state_full = STATE_NAME_MAP.get(state, state)
    # Use area search: find the city area within the state, then query within it
    tag_nodes = "\n  ".join(
        f'node{tag}(area.city_area);' for tag in HVAC_TAG_FILTERS
    )
    tag_ways = "\n  ".join(
        f'way{tag}(area.city_area);' for tag in HVAC_TAG_FILTERS
    )
    return f"""[out:json][timeout:30];
area["name"="{state_full}"]["admin_level"="4"]->.state_area;
area["name"="{city}"](area.state_area)->.city_area;
(
  {tag_nodes}
  {tag_ways}
);
out body center;"""


class OSMScout:
    """Free-tier HVAC discovery using OpenStreetMap Overpass API."""

    async def search_city(
        self, city: str, state: str, max_results: int = 30
    ) -> list[dict]:
        """Return up to max_results HVAC companies from OSM for the given city."""
        query = _build_overpass_query(city, state)
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.get(
                    OVERPASS_URL,
                    params={"data": query},
                    headers={"User-Agent": "HVACIntelPlatform/1.0"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning(f"OSM query failed for {city}, {state}: {exc}")
            return []

        companies = []
        seen_names: set[str] = set()
        for element in data.get("elements", []):
            company = _osm_element_to_company(element, city, state)
            if company and company["name"] not in seen_names:
                seen_names.add(company["name"])
                companies.append(company)
                if len(companies) >= max_results:
                    break

        logger.info(f"OSM: found {len(companies)} HVAC businesses in {city}, {state}")
        return companies

    async def run_batch(
        self,
        cities: list[tuple[str, str]],
        max_per_city: int = 30,
        progress_callback: Optional[Callable] = None,
    ) -> list[dict]:
        """Run search across multiple cities. Returns deduplicated company list."""
        all_companies: list[dict] = []
        seen_place_ids: set[str] = set()

        for i, (city, state) in enumerate(cities):
            companies = await self.search_city(city, state, max_results=max_per_city)
            for c in companies:
                if c["place_id"] not in seen_place_ids:
                    seen_place_ids.add(c["place_id"])
                    all_companies.append(c)

            if progress_callback:
                progress = (i + 1) / len(cities)
                msg = f"OSM: scanned {i + 1}/{len(cities)} cities ({len(all_companies)} found)"
                try:
                    result = progress_callback(msg, progress)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

            # Polite delay between Overpass API requests
            if i < len(cities) - 1:
                await asyncio.sleep(1.0)

        return all_companies
