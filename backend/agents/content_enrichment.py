"""
ContentEnrichmentAgent — Semantic website signal extraction using Firecrawl.

Runs after the existing EnrichmentAgent (which handles SSL, domain age, tech stack).
Visits company websites and extracts business-specific signals that influence scoring.
"""
import asyncio
import re
import logging
from datetime import date
from typing import Optional
from firecrawl import FirecrawlApp

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year

# Firecrawl extraction schema for business signals
CONTENT_SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "years_in_business": {
            "type": "integer",
            "description": "Number of years the business has been operating, if mentioned",
        },
        "is_family_owned": {
            "type": "boolean",
            "description": "True if website says family-owned or family business",
        },
        "offers_24_7": {
            "type": "boolean",
            "description": "True if website advertises 24/7 or round-the-clock service",
        },
        "service_count": {
            "type": "integer",
            "description": "Estimated number of distinct HVAC services offered",
        },
        "is_recruiting": {
            "type": "boolean",
            "description": "True if website has job listings, 'now hiring', or 'join our team'",
        },
        "technician_count": {
            "type": "integer",
            "description": "Number of technicians mentioned (e.g. 'our team of 12 technicians')",
        },
        "serves_commercial": {
            "type": "boolean",
            "description": "True if website mentions commercial or industrial HVAC services",
        },
    },
}


def extract_content_signals(text: str) -> dict:
    """
    Fallback regex extractor for when Firecrawl AI extraction is unavailable.
    Also used to validate Firecrawl output and fill gaps.
    """
    if not text:
        return {
            "is_family_owned": False,
            "offers_24_7": False,
            "years_in_business": None,
            "service_count": 0,
            "is_recruiting": False,
            "technician_count": None,
            "serves_commercial": False,
        }

    t = text.lower()

    # Family ownership
    family_owned = bool(re.search(
        r"family[\s\-]owned|family business|father and son|mother and son|locally owned|owner operated",
        t
    ))

    # 24/7 service
    offers_24_7 = bool(re.search(
        r"24/7|24 hours|twenty.four hours|around the clock|always available|emergency service",
        t
    ))

    # Years in business — look for "since YYYY" or "founded YYYY"
    years = None
    since_match = re.search(r"(?:since|founded|established|serving since|est\.?\s*)\s*(19\d{2}|20[0-1]\d)", t)
    if since_match:
        founding_year = int(since_match.group(1))
        years = CURRENT_YEAR - founding_year

    # Technician count
    tech_match = re.search(
        r"(?:team of|fleet of|over|more than)?\s*(\d+)\s+(?:certified\s+)?technicians?",
        t
    )
    tech_count = int(tech_match.group(1)) if tech_match else None

    # Recruiting
    is_recruiting = bool(re.search(
        r"now hiring|we.re hiring|join our team|careers|open position|apply now|technician opening",
        t
    ))

    # Commercial
    serves_commercial = bool(re.search(
        r"commercial|industrial|office building|retail|restaurant|property management",
        t
    ))

    # Service count — count distinct HVAC service keywords
    service_keywords = [
        "installation", "repair", "maintenance", "replacement", "tune.up",
        "duct", "air quality", "thermostat", "heat pump", "refrigeration",
        "geothermal", "mini.split", "zoning", "ventilation", "filtration",
    ]
    service_count = sum(1 for kw in service_keywords if re.search(kw, t))

    return {
        "is_family_owned": family_owned,
        "offers_24_7": offers_24_7,
        "years_in_business": years,
        "service_count": service_count,
        "is_recruiting": is_recruiting,
        "technician_count": tech_count,
        "serves_commercial": serves_commercial,
    }


class ContentEnrichmentAgent:
    """Extract semantic business signals from company websites using Firecrawl."""

    def __init__(self, api_key: str):
        self.app = FirecrawlApp(api_key=api_key)

    async def enrich_company(self, company: dict) -> dict:
        """
        Visit company website and extract content signals.
        Returns a dict of new fields to merge into the company record.
        All fields default to safe None/False values if extraction fails.
        """
        base = {
            "is_family_owned_likely": None,
            "offers_24_7": None,
            "service_count_estimated": None,
            "years_in_business_claimed": None,
            "is_recruiting": None,
            "technician_count_estimated": None,
            "serves_commercial": None,
            "content_enriched": False,
        }

        website = company.get("website")
        if not website or not company.get("website_active"):
            return base

        try:
            result = await asyncio.to_thread(
                self.app.scrape_url,
                website,
                formats=["extract"],
                extract={
                    "schema": CONTENT_SIGNAL_SCHEMA,
                    "prompt": (
                        "Extract business information from this HVAC contractor website. "
                        "Focus on years in business, family ownership, 24/7 service, "
                        "service offerings, hiring, technician count, and commercial services."
                    ),
                },
            )

            # Handle both object and dict response styles
            ai_signals = getattr(result, "extract", None)
            if ai_signals is None and isinstance(result, dict):
                ai_signals = result.get("extract", {})

            # Also get markdown for fallback regex check
            _md_raw = getattr(result, "markdown", None)
            if not isinstance(_md_raw, str):
                _md_raw = result.get("markdown", "") if isinstance(result, dict) else ""
            md = _md_raw or ""
            regex_signals = extract_content_signals(md)

            # Prefer AI extraction, fall back to regex where AI returned None
            def pick(ai_key: str, regex_key: str):
                ai_val = (ai_signals or {}).get(ai_key)
                return ai_val if ai_val is not None else regex_signals.get(regex_key)

            return {
                "is_family_owned_likely": pick("is_family_owned", "is_family_owned"),
                "offers_24_7": pick("offers_24_7", "offers_24_7"),
                "service_count_estimated": pick("service_count", "service_count"),
                "years_in_business_claimed": pick("years_in_business", "years_in_business"),
                "is_recruiting": pick("is_recruiting", "is_recruiting"),
                "technician_count_estimated": pick("technician_count", "technician_count"),
                "serves_commercial": pick("serves_commercial", "serves_commercial"),
                "content_enriched": True,
            }

        except Exception as e:
            logger.warning(f"ContentEnrichment failed for {company.get('name')}: {e}")
            return base

    async def enrich_batch(
        self,
        companies: list[dict],
        progress_callback=None,
    ) -> list[dict]:
        """Enrich a list of companies, respecting rate limits. Returns enriched list."""
        total = len(companies)
        for i, company in enumerate(companies):
            signals = await self.enrich_company(company)
            company.update(signals)
            if progress_callback:
                await progress_callback(
                    f"Content enriched {i + 1}/{total}: {company.get('name', '')}",
                    i / total,
                )
            await asyncio.sleep(0.3)
        return companies
