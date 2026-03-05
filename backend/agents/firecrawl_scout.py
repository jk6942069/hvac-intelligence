"""
FirecrawlScout — Real HVAC company discovery using the Firecrawl API.

Primary source: Firecrawl web search (Google-indexed results, stable).
Secondary source: Yellow Pages structured extract.
Falls back to mock Scout when FIRECRAWL_API_KEY is not set.
"""
import asyncio
import re
import logging
from typing import Optional
from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)

# National chains to filter out
CHAIN_PATTERNS = [
    r"one hour heating", r"lennox", r"carrier", r"trane dealer",
    r"american home shield", r"cool today", r"horizon services",
    r"service experts", r"aire serv", r"comfort systems usa",
    r"fred's heating", r"bob's heating",
]

PREMIUM_STATES = {"AZ", "TX", "FL", "TN", "NC", "GA", "SC", "NV", "CO", "VA"}


def is_national_chain(name: str) -> bool:
    """Return True if the company name matches a known national chain."""
    name_lower = name.lower()
    return any(re.search(p, name_lower) for p in CHAIN_PATTERNS)


def normalize_company_key(name: str, phone: str, address: str) -> str:
    """
    Produce a normalized deduplication key.
    Strips punctuation, takes last 7 digits of phone, takes street number prefix.

    Note: Only legal-entity suffixes (LLC, Inc, Corp, Co, Company) are stripped.
    Industry words (heating, cooling, air, HVAC, services) are deliberately kept
    to prevent false deduplication between distinct companies with similar geographic names.
    Known limitation: abbreviations (AC vs. "Air Conditioning") may produce different
    keys for the same company — this is acceptable for this use case.
    """
    # Normalize name: strip non-alpha, lowercase, remove legal entity suffixes only
    clean_name = re.sub(r"[^a-z0-9]", "", re.sub(
        r"\b(llc|inc|corp|co|company)\b", "",
        name.lower()
    ))
    # Normalize phone: digits only, last 7
    digits = re.sub(r"\D", "", phone)
    phone_suffix = digits[-7:] if len(digits) >= 7 else digits
    # Normalize address: first numeric token
    addr_num = re.match(r"^(\d+)", address.strip())
    addr_prefix = addr_num.group(1) if addr_num else ""

    return f"{clean_name}|{phone_suffix}|{addr_prefix}"


class FirecrawlScout:
    """Discover HVAC companies using Firecrawl search + Yellow Pages extract."""

    def __init__(self, api_key: str):
        self.app = FirecrawlApp(api_key=api_key)
        self._seen_keys: set[str] = set()

    def _add_to_seen(self, company: dict) -> None:
        key = normalize_company_key(
            company.get("name", ""),
            company.get("phone", ""),
            company.get("address", ""),
        )
        self._seen_keys.add(key)

    def _is_duplicate(self, company: dict) -> bool:
        key = normalize_company_key(
            company.get("name", ""),
            company.get("phone", ""),
            company.get("address", ""),
        )
        return key in self._seen_keys

    def _parse_search_result(self, item: dict, city: str, state: str) -> Optional[dict]:
        """
        Parse a single Firecrawl search result into a company dict.
        Search results contain: title, url, description, markdown.
        We extract what we can from the description/title; full enrichment
        happens downstream in the EnrichmentAgent.
        """
        name = item.get("title", "").strip()
        if not name or is_national_chain(name):
            return None

        # Try to pull phone from description
        desc = item.get("description", "") + " " + item.get("markdown", "")
        phone_match = re.search(r"(\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})", desc)
        phone = phone_match.group(1) if phone_match else ""

        # Try to pull rating
        rating_match = re.search(r"(\d+\.?\d*)\s*star", desc, re.I)
        rating = float(rating_match.group(1)) if rating_match else None

        # Try to pull review count
        review_match = re.search(r"(\d+)\s+review", desc, re.I)
        reviews = int(review_match.group(1)) if review_match else None

        return {
            "name": name,
            "city": city,
            "state": state,
            "phone": phone,
            "address": "",
            "website": item.get("url", ""),
            "google_rating": rating,
            "google_review_count": reviews,
            "category": "HVAC",
            "discovery_source": "firecrawl_search",
        }

    async def _search_tier1(self, city: str, state: str, max_results: int) -> list[dict]:
        """Tier 1: Firecrawl web search for HVAC companies."""
        queries = [
            f"HVAC contractor {city} {state}",
            f"air conditioning repair {city} {state}",
        ]
        companies = []
        for query in queries:
            try:
                result = await asyncio.to_thread(
                    self.app.search, query, limit=max_results // 2
                )
                items = result.get("data", []) if isinstance(result, dict) else (result or [])
                for item in items:
                    parsed = self._parse_search_result(item, city, state)
                    if parsed and not self._is_duplicate(parsed):
                        self._add_to_seen(parsed)
                        companies.append(parsed)
            except Exception as e:
                logger.warning(f"Firecrawl search failed for '{query}': {e}")
        return companies

    async def _scrape_yellowpages(self, city: str, state: str) -> list[dict]:
        """Tier 2: Structured extract from Yellow Pages listing page."""
        url = (
            f"https://www.yellowpages.com/search"
            f"?search_terms=hvac+contractor"
            f"&geo_location_terms={city.replace(' ', '+')}%2C+{state}"
        )
        schema = {
            "type": "object",
            "properties": {
                "businesses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "phone": {"type": "string"},
                            "address": {"type": "string"},
                            "rating": {"type": "number"},
                            "review_count": {"type": "integer"},
                            "website": {"type": "string"},
                            "years_in_business": {"type": "integer"},
                        },
                    },
                }
            },
        }
        try:
            result = await asyncio.to_thread(
                self.app.scrape_url,
                url,
                formats=["extract"],
                extract={"schema": schema, "prompt": "Extract all HVAC business listings from this Yellow Pages search result page."},
            )
            # firecrawl-py returns ScrapeResponse; access .extract or ['extract']
            extract = getattr(result, "extract", None) or (result.get("extract") if isinstance(result, dict) else None) or {}
            businesses = extract.get("businesses", []) if extract else []
        except Exception as e:
            logger.warning(f"Yellow Pages scrape failed for {city}, {state}: {e}")
            return []

        companies = []
        for biz in (businesses or []):
            if not biz.get("name") or is_national_chain(biz.get("name", "")):
                continue
            company = {
                "name": biz.get("name", "").strip(),
                "city": city,
                "state": state,
                "phone": biz.get("phone", ""),
                "address": biz.get("address", ""),
                "website": biz.get("website", ""),
                "google_rating": biz.get("rating"),
                "google_review_count": biz.get("review_count"),
                "category": "HVAC",
                "discovery_source": "yellowpages",
            }
            if not self._is_duplicate(company):
                self._add_to_seen(company)
                companies.append(company)
        return companies

    async def search_city(self, city: str, state: str, max_results: int = 40) -> list[dict]:
        """
        Discover HVAC companies in a city using Tier 1 (web search) +
        Tier 2 (Yellow Pages) in parallel. Returns deduplicated list.
        """
        tier1, tier2 = await asyncio.gather(
            self._search_tier1(city, state, max_results),
            self._scrape_yellowpages(city, state),
            return_exceptions=True,
        )
        combined = []
        for result in [tier1, tier2]:
            if isinstance(result, Exception):
                logger.warning(f"Scout tier failed: {result}")
            else:
                combined.extend(result)
        return combined[:max_results]

    async def run_batch(
        self,
        cities: list[tuple[str, str]],
        max_per_city: int = 30,
    ) -> list[dict]:
        """Run discovery for all cities, respecting rate limits."""
        all_companies = []
        for city, state in cities:
            try:
                companies = await self.search_city(city, state, max_per_city)
                all_companies.extend(companies)
                logger.info(f"Scout: {len(companies)} from {city}, {state}")
                await asyncio.sleep(0.5)  # Polite delay between cities
            except Exception as e:
                logger.exception(f"Scout failed for {city}, {state}: {e}")
        return all_companies
