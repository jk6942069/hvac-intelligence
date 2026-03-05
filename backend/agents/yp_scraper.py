"""
YPScraper — Yellow Pages HTML scraping fallback for HVAC discovery.

Used when OSMScout returns < 5 results for a city. No API key required.
Scrapes yellowpages.com search results using HTTPX + BeautifulSoup.
"""
import asyncio
import hashlib
import logging
import httpx
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

YP_SEARCH_URL = "https://www.yellowpages.com/search"
YP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
OSM_FALLBACK_THRESHOLD = 5   # Use YP when OSM returns fewer than this many results


def _parse_yp_listing(listing, city: str, state: str) -> Optional[dict]:
    """Parse a single .result.organic element into a company dict."""
    name_el = listing.select_one(".business-name")
    if not name_el:
        return None
    name = name_el.get_text(strip=True)
    if not name:
        return None

    phone_el = listing.select_one(".phones .full-number")
    phone = phone_el.get_text(strip=True) if phone_el else None

    street_el = listing.select_one(".street-address")
    city_el = listing.select_one(".city")
    state_el = listing.select_one(".state")
    street = street_el.get_text(strip=True) if street_el else ""
    listing_city = city_el.get_text(strip=True) if city_el else city
    listing_state = state_el.get_text(strip=True) if state_el else state
    address_parts = [p for p in [street, listing_city, listing_state] if p]
    address = ", ".join(address_parts) if address_parts else f"{city}, {state}"

    website_el = listing.select_one("a.track-visit-website")
    website = website_el.get("href") if website_el else None

    # Stable place_id: hash of name + city so re-runs don't create duplicates
    key = f"{name.lower()}-{city.lower()}-{state.lower()}"
    place_id = f"yp_{hashlib.md5(key.encode()).hexdigest()[:12]}"

    return {
        "place_id": place_id,
        "name": name,
        "address": address,
        "city": listing_city or city,
        "state": listing_state or state,
        "phone": phone,
        "website": website,
        "google_rating": None,
        "google_review_count": 0,
        "category": "HVAC",
        "raw_google_data": {"source": "yellowpages"},
    }


class YPScraper:
    """Yellow Pages HVAC business scraper — no API key required."""

    async def search_city(
        self, city: str, state: str, max_results: int = 30
    ) -> list[dict]:
        """Scrape Yellow Pages for HVAC businesses in the given city."""
        params = {
            "search_terms": "hvac contractor",
            "geo_location": f"{city}, {state}",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(YP_SEARCH_URL, params=params, headers=YP_HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            logger.warning(f"YP scrape failed for {city}, {state}: {exc}")
            return []

        soup = BeautifulSoup(html, "html.parser")
        listings = soup.select(".result.organic")

        companies = []
        seen_place_ids: set[str] = set()
        for listing in listings:
            company = _parse_yp_listing(listing, city, state)
            if company and company["place_id"] not in seen_place_ids:
                seen_place_ids.add(company["place_id"])
                companies.append(company)
                if len(companies) >= max_results:
                    break

        logger.info(f"YPScraper: found {len(companies)} businesses in {city}, {state}")
        return companies
