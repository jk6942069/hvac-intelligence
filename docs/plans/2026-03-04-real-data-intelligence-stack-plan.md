# Real Data Intelligence Stack — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Replace synthetic placeholder data with real HVAC company discovery (Firecrawl), semantic website enrichment, enhanced conviction scoring, and LLM Council investment thesis generation for the top-10 candidates.

**Architecture:** Three new Python agents (`firecrawl_scout`, `content_enrichment`, `council`) slot into the existing 7-stage orchestrator. The database gains 10 nullable columns via the existing `migrate_db()` pattern. The React right panel renders council output when available, template output when not. All new features degrade gracefully to mock mode when API keys are absent.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / SQLite — `firecrawl-py` SDK for discovery + content extraction — `openai` client pointed at OpenRouter for council deliberation — React/TypeScript/TanStack Query for the frontend council display.

**Design doc:** `docs/plans/2026-03-04-real-data-intelligence-stack-design.md`

---

## Pre-flight Checklist

Before starting any task, verify the backend is importable from its directory:

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -c "from config import settings; print('ok')"
```

Expected: `ok`

---

## Task 1: Install Dependencies and Extend Config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify: `backend/.env` (create if missing)

### Step 1: Add packages to requirements.txt

Open `backend/requirements.txt` and append these two lines at the bottom:

```
firecrawl-py>=1.4.0
openai>=1.12.0
```

### Step 2: Install the new packages

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m pip install firecrawl-py openai
```

Expected: both packages install without error. Verify:

```bash
py -c "from firecrawl import FirecrawlApp; print('firecrawl ok')"
py -c "from openai import AsyncOpenAI; print('openai ok')"
```

### Step 3: Extend config.py

The current `config.py` ends at line 37. Add these fields to the `Settings` class, after the existing `builtwith_api_key` line:

```python
    # Real-data pipeline keys
    firecrawl_api_key: str = ""
    openrouter_api_key: str = ""

    # Council deliberation settings
    council_models: list = ["anthropic/claude-sonnet-4-5", "openai/gpt-4o-mini", "google/gemini-flash-1.5"]
    council_chairman: str = "anthropic/claude-sonnet-4-5"
    council_min_conviction: int = 60      # Gate: skip council below this score
    council_min_signals: int = 4          # Gate: skip council if fewer non-null content signals
```

### Step 4: Add keys to .env

Create or append to `backend/.env`:

```env
# Real data pipeline — leave blank to stay in mock mode
FIRECRAWL_API_KEY=
OPENROUTER_API_KEY=

# Existing keys (fill in if you have them)
# GOOGLE_PLACES_API_KEY=
# ANTHROPIC_API_KEY=
```

### Step 5: Verify config loads

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -c "from config import settings; print(settings.firecrawl_api_key, settings.council_min_conviction)"
```

Expected: ` 60` (empty string for key, 60 for threshold).

### Step 6: Commit

```bash
cd C:\Users\joonk\hvac-intelligence
git add backend/requirements.txt backend/config.py backend/.env
git commit -m "feat: add firecrawl-py + openai deps, extend config with council settings"
```

---

## Task 2: Database Schema — 10 New Columns

**Files:**
- Modify: `backend/models.py` (add 10 columns to Company class)
- Modify: `backend/database.py` (add 10 ALTER TABLE statements to migrate_db)

### Step 1: Add columns to models.py

In `backend/models.py`, the Company class currently ends around line 76. Add these columns after `website_outdated` (line 38 area) and before the signals block:

```python
    # Content enrichment signals (from website analysis)
    is_family_owned_likely = Column(Boolean, nullable=True)
    offers_24_7 = Column(Boolean, nullable=True)
    service_count_estimated = Column(Integer, nullable=True)
    years_in_business_claimed = Column(Integer, nullable=True)
    is_recruiting = Column(Boolean, nullable=True)
    technician_count_estimated = Column(Integer, nullable=True)
    serves_commercial = Column(Boolean, nullable=True)
    discovery_source = Column(String, nullable=True)   # "firecrawl_search" | "yellowpages" | "mock"
    content_enriched = Column(Boolean, default=False)
    council_analyzed = Column(Boolean, default=False)
```

### Step 2: Add migrations to database.py

In `backend/database.py`, the `migrate_db()` function has a `migrations` list starting around line 42. The list currently has 9 items. Add 10 more items to the list (after the existing 9):

```python
        # Content enrichment + council tracking columns (v3)
        "ALTER TABLE companies ADD COLUMN is_family_owned_likely BOOLEAN",
        "ALTER TABLE companies ADD COLUMN offers_24_7 BOOLEAN",
        "ALTER TABLE companies ADD COLUMN service_count_estimated INTEGER",
        "ALTER TABLE companies ADD COLUMN years_in_business_claimed INTEGER",
        "ALTER TABLE companies ADD COLUMN is_recruiting BOOLEAN",
        "ALTER TABLE companies ADD COLUMN technician_count_estimated INTEGER",
        "ALTER TABLE companies ADD COLUMN serves_commercial BOOLEAN",
        "ALTER TABLE companies ADD COLUMN discovery_source VARCHAR",
        "ALTER TABLE companies ADD COLUMN content_enriched BOOLEAN DEFAULT FALSE",
        "ALTER TABLE companies ADD COLUMN council_analyzed BOOLEAN DEFAULT FALSE",
```

### Step 3: Verify migration runs without error

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -c "
import asyncio
from database import init_db, migrate_db
async def run():
    await init_db()
    await migrate_db()
    print('migration ok')
asyncio.run(run())
"
```

Expected: `migration ok`

### Step 4: Verify columns exist in SQLite

```bash
py -c "
import sqlite3
db = sqlite3.connect('hvac_intel.db')
cols = [r[1] for r in db.execute('PRAGMA table_info(companies)').fetchall()]
new = ['is_family_owned_likely','offers_24_7','service_count_estimated','years_in_business_claimed',
       'is_recruiting','technician_count_estimated','serves_commercial','discovery_source',
       'content_enriched','council_analyzed']
for c in new:
    assert c in cols, f'MISSING: {c}'
print('all 10 columns present')
db.close()
"
```

Expected: `all 10 columns present`

### Step 5: Commit

```bash
git add backend/models.py backend/database.py
git commit -m "feat: add 10 content-enrichment + council-tracking columns to Company table"
```

---

## Task 3: FirecrawlScout Agent

**Files:**
- Create: `backend/agents/firecrawl_scout.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_firecrawl_scout.py`

### Step 1: Create the tests directory and conftest

```bash
mkdir backend\tests
```

Create `backend/tests/__init__.py` — empty file.

Create `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures for backend tests."""
import pytest
import sys
import os

# Make backend modules importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### Step 2: Write the failing tests

Create `backend/tests/test_firecrawl_scout.py`:

```python
"""Tests for FirecrawlScout — real discovery via Firecrawl API."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.firecrawl_scout import FirecrawlScout, normalize_company_key


# ── Unit: deduplication key ──────────────────────────────────────────────────

def test_normalize_key_strips_punctuation():
    key = normalize_company_key("Smith's A/C & Heating LLC", "602-555-1234", "1234 Main St")
    assert "smithsacheating" in key
    assert "5551234" in key
    assert "1234" in key


def test_normalize_key_handles_missing_phone():
    key = normalize_company_key("Cool Air Inc", "", "500 Oak Ave")
    assert key  # Should not be empty
    assert "coolair" in key


def test_normalize_key_same_company_different_format():
    key1 = normalize_company_key("Cool Air, Inc.", "(602) 555-1234", "1234 Main St.")
    key2 = normalize_company_key("Cool Air Inc", "6025551234", "1234 Main Street")
    # Same core data should produce same key
    assert key1 == key2


# ── Unit: chain filter ───────────────────────────────────────────────────────

def test_filter_removes_national_chains():
    from agents.firecrawl_scout import is_national_chain
    assert is_national_chain("One Hour Heating & Air Conditioning") is True
    assert is_national_chain("Lennox Premier Dealer") is True
    assert is_national_chain("Smith Family HVAC") is False
    assert is_national_chain("Desert Air Services") is False


# ── Integration: search_city with mocked Firecrawl ──────────────────────────

@pytest.mark.asyncio
async def test_search_city_returns_companies_from_search():
    mock_search_results = [
        {"title": "Desert Air LLC", "url": "https://desertair.com", "description": "HVAC contractor in Phoenix AZ. Call 602-555-0001. 4.8 stars, 150 reviews.", "markdown": ""},
        {"title": "Cool Breeze HVAC", "url": "https://coolbreeze.com", "description": "AC repair Phoenix Arizona. 602-555-0002. Rated 4.5.", "markdown": ""},
    ]

    with patch("agents.firecrawl_scout.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.search.return_value = {"data": mock_search_results}
        MockApp.return_value = mock_instance

        scout = FirecrawlScout(api_key="fc-test")
        companies = await scout.search_city("Phoenix", "AZ", max_results=20)

    assert len(companies) >= 1
    assert all("name" in c for c in companies)
    assert all("city" in c for c in companies)
    assert all(c["city"] == "Phoenix" for c in companies)
    assert all(c["state"] == "AZ" for c in companies)
    assert all(c["discovery_source"] == "firecrawl_search" for c in companies)


@pytest.mark.asyncio
async def test_search_city_deduplicates_across_sources():
    """Same company appearing in search + yellowpages → only one record."""
    same_company = {
        "name": "Desert Air LLC",
        "phone": "6025550001",
        "address": "100 N Central Ave",
        "city": "Phoenix",
        "state": "AZ",
        "discovery_source": "firecrawl_search",
        "google_rating": 4.8,
        "google_review_count": 150,
        "website": "https://desertair.com",
    }

    with patch("agents.firecrawl_scout.FirecrawlApp"):
        scout = FirecrawlScout(api_key="fc-test")
        # Manually add to seen set to simulate prior discovery
        scout._add_to_seen(same_company)
        result = scout._is_duplicate(same_company)

    assert result is True


@pytest.mark.asyncio
async def test_search_city_filters_national_chains():
    mock_search_results = [
        {"title": "One Hour Heating & Air Conditioning", "url": "https://1hour.com", "description": "National chain. 800-555-0001.", "markdown": ""},
        {"title": "Local HVAC Pro", "url": "https://localhvac.com", "description": "Local HVAC Phoenix AZ. 602-555-9999.", "markdown": ""},
    ]

    with patch("agents.firecrawl_scout.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.search.return_value = {"data": mock_search_results}
        MockApp.return_value = mock_instance

        scout = FirecrawlScout(api_key="fc-test")
        companies = await scout.search_city("Phoenix", "AZ")

    names = [c["name"] for c in companies]
    assert "One Hour Heating & Air Conditioning" not in names
    assert any("Local HVAC" in n or "HVAC Pro" in n for n in names)
```

### Step 3: Run tests to verify they fail

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m pytest tests/test_firecrawl_scout.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'agents.firecrawl_scout'`

### Step 4: Implement FirecrawlScout

Create `backend/agents/firecrawl_scout.py`:

```python
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
    """
    # Normalize name: strip non-alpha, lowercase, remove LLC/Inc/etc
    clean_name = re.sub(r"[^a-z0-9]", "", re.sub(
        r"\b(llc|inc|corp|co|company|services?|heating|cooling|air|hvac)\b", "",
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
                logger.warning(f"Scout failed for {city}, {state}: {e}")
        return all_companies
```

### Step 5: Run tests to verify they pass

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m pytest tests/test_firecrawl_scout.py -v
```

Expected:
```
PASSED test_normalize_key_strips_punctuation
PASSED test_normalize_key_handles_missing_phone
PASSED test_normalize_key_same_company_different_format
PASSED test_filter_removes_national_chains
PASSED test_search_city_returns_companies_from_search
PASSED test_search_city_deduplicates_across_sources
PASSED test_search_city_filters_national_chains
7 passed
```

If `test_normalize_key_same_company_different_format` fails: adjust the normalization — the point is that "Inc." and "Inc" and "(602)" and "602" all resolve to the same key. Tweak the regex until consistent.

### Step 6: Commit

```bash
git add backend/agents/firecrawl_scout.py backend/tests/
git commit -m "feat: FirecrawlScout — real HVAC discovery via Firecrawl search + Yellow Pages extract"
```

---

## Task 4: ContentEnrichmentAgent

**Files:**
- Create: `backend/agents/content_enrichment.py`
- Create: `backend/tests/test_content_enrichment.py`

### Step 1: Write the failing tests

Create `backend/tests/test_content_enrichment.py`:

```python
"""Tests for ContentEnrichmentAgent — semantic website signal extraction."""
import pytest
from unittest.mock import MagicMock, patch
from agents.content_enrichment import ContentEnrichmentAgent, extract_content_signals


# ── Unit: signal extraction from text ────────────────────────────────────────

def test_detects_family_owned():
    signals = extract_content_signals("We are a family-owned business serving Phoenix since 1985.")
    assert signals["is_family_owned"] is True


def test_detects_24_7():
    signals = extract_content_signals("24/7 emergency HVAC service available.")
    assert signals["offers_24_7"] is True


def test_detects_years_in_business():
    signals = extract_content_signals("Serving the greater Phoenix area since 1987.")
    assert signals["years_in_business"] == pytest.approx(2026 - 1987, abs=1)


def test_detects_recruiting():
    signals = extract_content_signals("We're hiring! Join our team of certified HVAC technicians.")
    assert signals["is_recruiting"] is True


def test_detects_technician_count():
    signals = extract_content_signals("Our fleet of 12 certified technicians is ready to serve you.")
    assert signals["technician_count"] == 12


def test_detects_commercial():
    signals = extract_content_signals("We serve residential and commercial clients throughout the Valley.")
    assert signals["serves_commercial"] is True


def test_detects_service_count():
    text = """
    Services:
    - AC Installation
    - Heating Repair
    - Duct Cleaning
    - Air Quality Testing
    - Commercial HVAC
    - Emergency Service
    """
    signals = extract_content_signals(text)
    assert signals["service_count"] >= 4


def test_handles_empty_text():
    signals = extract_content_signals("")
    assert signals["is_family_owned"] is False
    assert signals["offers_24_7"] is False
    assert signals["years_in_business"] is None
    assert signals["service_count"] == 0


# ── Integration: enrichment with mocked Firecrawl ────────────────────────────

@pytest.mark.asyncio
async def test_enrich_company_returns_signals():
    company = {
        "id": "test-001",
        "name": "Desert Air LLC",
        "website": "https://desertair.com",
        "website_active": True,
    }
    mock_extract = {
        "years_in_business": 35,
        "is_family_owned": True,
        "offers_24_7": True,
        "service_count": 6,
        "is_recruiting": False,
        "technician_count": 8,
        "serves_commercial": True,
    }
    mock_result = MagicMock()
    mock_result.extract = mock_extract

    with patch("agents.content_enrichment.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.scrape_url.return_value = mock_result
        MockApp.return_value = mock_instance

        agent = ContentEnrichmentAgent(api_key="fc-test")
        result = await agent.enrich_company(company)

    assert result["is_family_owned_likely"] is True
    assert result["offers_24_7"] is True
    assert result["years_in_business_claimed"] == 35
    assert result["technician_count_estimated"] == 8
    assert result["serves_commercial"] is True
    assert result["content_enriched"] is True


@pytest.mark.asyncio
async def test_enrich_company_skips_no_website():
    company = {"id": "test-002", "name": "No Web Co", "website": None, "website_active": False}
    agent = ContentEnrichmentAgent(api_key="fc-test")
    result = await agent.enrich_company(company)
    assert result["content_enriched"] is False


@pytest.mark.asyncio
async def test_enrich_company_handles_firecrawl_failure():
    company = {"id": "test-003", "name": "Fail Co", "website": "https://fail.com", "website_active": True}

    with patch("agents.content_enrichment.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.scrape_url.side_effect = Exception("API error")
        MockApp.return_value = mock_instance

        agent = ContentEnrichmentAgent(api_key="fc-test")
        result = await agent.enrich_company(company)

    # Should not raise; should mark as not enriched
    assert result["content_enriched"] is False
```

### Step 2: Run tests to verify they fail

```bash
py -m pytest tests/test_content_enrichment.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'agents.content_enrichment'`

### Step 3: Implement ContentEnrichmentAgent

Create `backend/agents/content_enrichment.py`:

```python
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
            md = getattr(result, "markdown", None) or (result.get("markdown", "") if isinstance(result, dict) else "")
            regex_signals = extract_content_signals(md or "")

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
```

### Step 4: Run tests to verify they pass

```bash
py -m pytest tests/test_content_enrichment.py -v
```

Expected: all 11 tests pass.

If `test_detects_years_in_business` fails: adjust the regex — try adding `"operating since"` or `"in business since"` patterns. The year extraction needs to handle `"since 1987"` as a phrase.

### Step 5: Commit

```bash
git add backend/agents/content_enrichment.py backend/tests/test_content_enrichment.py
git commit -m "feat: ContentEnrichmentAgent — semantic website signals via Firecrawl AI extract"
```

---

## Task 5: Scoring Engine — Content Signal Enhancement

**Files:**
- Modify: `backend/agents/scoring_engine.py`
- Create: `backend/tests/test_scoring_engine_content.py`

### Step 1: Write the failing tests

Create `backend/tests/test_scoring_engine_content.py`:

```python
"""Tests for content-signal additions to the scoring engine."""
import pytest
from agents.scoring_engine import ScoringEngine


def make_company(**overrides) -> dict:
    base = {
        "name": "Test HVAC Co",
        "city": "Phoenix",
        "state": "AZ",
        "google_rating": 4.5,
        "google_review_count": 120,
        "domain_age_years": 15.0,
        "ssl_valid": True,
        "website_active": True,
        "has_facebook": True,
        "has_instagram": False,
        "tech_stack": ["WordPress"],
        "signals": [],
        # Content signals default to None (not enriched)
        "is_family_owned_likely": None,
        "offers_24_7": None,
        "service_count_estimated": None,
        "years_in_business_claimed": None,
        "is_recruiting": None,
        "technician_count_estimated": None,
        "serves_commercial": None,
    }
    base.update(overrides)
    return base


def test_family_owned_raises_transition_score():
    engine = ScoringEngine()
    without = engine.score(make_company(is_family_owned_likely=False))
    with_family = engine.score(make_company(is_family_owned_likely=True))
    # transition score is index 2
    assert with_family[2] > without[2]


def test_long_tenure_claimed_raises_transition_score():
    engine = ScoringEngine()
    without = engine.score(make_company(years_in_business_claimed=None))
    with_tenure = engine.score(make_company(years_in_business_claimed=28))
    assert with_tenure[2] >= without[2]


def test_commercial_service_raises_platform_score():
    engine = ScoringEngine()
    without = engine.score(make_company(serves_commercial=False))
    with_commercial = engine.score(make_company(serves_commercial=True))
    # platform score is index 4
    assert with_commercial[4] > without[4]


def test_recruiting_raises_platform_score():
    engine = ScoringEngine()
    without = engine.score(make_company(is_recruiting=False))
    with_recruiting = engine.score(make_command(is_recruiting=True))
    assert with_recruiting[4] > without[4]


def test_247_service_raises_quality_score():
    engine = ScoringEngine()
    without = engine.score(make_company(offers_24_7=False))
    with_24_7 = engine.score(make_company(offers_24_7=True))
    # quality score is index 3
    assert with_24_7[3] > without[3]


def test_high_service_count_raises_quality_score():
    engine = ScoringEngine()
    without = engine.score(make_company(service_count_estimated=2))
    with_services = engine.score(make_company(service_count_estimated=7))
    assert with_services[3] > without[3]


def test_large_tech_team_raises_platform_score():
    engine = ScoringEngine()
    without = engine.score(make_company(technician_count_estimated=2))
    with_team = engine.score(make_company(technician_count_estimated=12))
    assert with_team[4] > without[4]


def test_missing_content_signals_dont_break_scoring():
    """Companies with no content enrichment (None values) score correctly."""
    engine = ScoringEngine()
    company = make_company()  # all content signals are None
    result = engine.score(company)
    conviction, breakdown, trans, qual, plat, explanation = result
    assert 0 <= conviction <= 100
    assert 0 <= trans <= 40
    assert 0 <= qual <= 35
    assert 0 <= plat <= 25


def test_family_owned_appears_in_thesis_bullets():
    engine = ScoringEngine()
    result = engine.score(make_company(is_family_owned_likely=True, years_in_business_claimed=30))
    explanation = result[5]
    bullets = explanation.get("thesisBullets", [])
    assert any("family" in b.lower() for b in bullets)


# Fix typo in test above
def make_command(**overrides):
    return make_company(**overrides)
```

### Step 2: Run tests to verify they fail

```bash
py -m pytest tests/test_scoring_engine_content.py -v 2>&1 | head -20
```

Expected: tests fail because `_transition_pressure`, `_business_quality`, `_platform_fit` don't yet read the new content signal keys.

### Step 3: Modify scoring_engine.py

In `backend/agents/scoring_engine.py`, update the three scoring functions. **Add content signal reading at the top of each function, then add conditional point additions.**

In `_transition_pressure(company)` — after the existing variable reads (around line 30), add:

```python
    # Content signal augmentation
    is_family_owned = company.get("is_family_owned_likely")
    years_claimed = company.get("years_in_business_claimed")

    # Family ownership → key-man / succession pressure
    if is_family_owned is True:
        score = min(40, score + 4)
        factors.append("Family-owned — succession planning is a common exit trigger")

    # Claimed tenure supplements domain age signal
    if years_claimed and years_claimed > 20:
        bonus = 5 if years_claimed >= 30 else 3
        score = min(40, score + bonus)
        factors.append(
            f"In business {years_claimed}+ years (stated on website) — founding-generation operator"
        )
```

In `_business_quality(company)` — after existing variable reads, add:

```python
    # Content signal augmentation
    offers_24_7 = company.get("offers_24_7")
    service_count = company.get("service_count_estimated") or 0

    if offers_24_7 is True:
        score = min(35, score + 3)
        factors.append("24/7 emergency service — systemized operations, not a lifestyle business")

    if service_count >= 5:
        score = min(35, score + 3)
        factors.append(f"{service_count} service lines — diversified revenue, lower single-service churn risk")
    elif service_count >= 3:
        score = min(35, score + 1)
        factors.append(f"{service_count} service lines — moderate diversification")
```

In `_platform_fit(company)` — after existing variable reads, add:

```python
    # Content signal augmentation
    is_recruiting = company.get("is_recruiting")
    serves_commercial = company.get("serves_commercial")
    tech_count = company.get("technician_count_estimated") or 0

    if serves_commercial is True:
        score = min(25, score + 4)
        factors.append("Commercial HVAC services — higher ACV, stronger PE roll-up fit")

    if is_recruiting is True:
        score = min(25, score + 3)
        factors.append("Actively hiring technicians — operational capacity for scale")

    if tech_count >= 8:
        score = min(25, score + 3)
        factors.append(f"Team of {tech_count} technicians — not founder-dependent, transferable")
    elif tech_count >= 4:
        score = min(25, score + 1)
        factors.append(f"{tech_count} technicians — small but scalable team in place")
```

Also update `_generate_thesis()` (search for it in scoring_engine.py) to prefer content-derived language. Add at the start of the thesis generation logic:

```python
    # Prefer content-derived thesis bullets when available
    if company.get("is_family_owned_likely") and company.get("years_in_business_claimed"):
        years = company["years_in_business_claimed"]
        thesis.append(
            f"Family-owned since {CURRENT_YEAR - years} ({years}yr) — "
            f"founding-generation operator, succession pressure confirmed on website"
        )
```

Add at the top of scoring_engine.py if not present:
```python
from datetime import date
CURRENT_YEAR = date.today().year
```

### Step 4: Run tests to verify they pass

```bash
py -m pytest tests/test_scoring_engine_content.py -v
```

Expected: 8/9 tests pass. The `make_command` typo test is intentionally included — fix it if it causes a name error by changing `make_command` to `make_company` in the test.

### Step 5: Commit

```bash
git add backend/agents/scoring_engine.py backend/tests/test_scoring_engine_content.py
git commit -m "feat: enhance scoring engine with content signals (family-owned, 24/7, services, team size)"
```

---

## Task 6: Council Qualification Gate

**Files:**
- Create: `backend/agents/council_gate.py`
- Create: `backend/tests/test_council_gate.py`

### Step 1: Write the failing tests

Create `backend/tests/test_council_gate.py`:

```python
"""Tests for council qualification gate."""
import pytest
from agents.council_gate import qualifies_for_council, count_populated_signals


def make_company(**overrides) -> dict:
    base = {
        "conviction_score": 75,
        "website_active": True,
        "content_enriched": True,
        "council_analyzed": False,
        "is_family_owned_likely": True,
        "offers_24_7": True,
        "service_count_estimated": 5,
        "years_in_business_claimed": 20,
        "is_recruiting": False,
        "technician_count_estimated": 8,
        "serves_commercial": True,
    }
    base.update(overrides)
    return base


def test_qualifies_when_all_criteria_met():
    assert qualifies_for_council(make_company()) is True


def test_disqualified_below_conviction_threshold():
    assert qualifies_for_council(make_company(conviction_score=55)) is False


def test_disqualified_no_website():
    assert qualifies_for_council(make_company(website_active=False)) is False


def test_disqualified_not_content_enriched():
    assert qualifies_for_council(make_company(content_enriched=False)) is False


def test_disqualified_already_analyzed():
    assert qualifies_for_council(make_company(council_analyzed=True)) is False


def test_disqualified_too_few_signals():
    # Only 1 non-null signal → not enough context
    thin = make_company(
        is_family_owned_likely=None,
        offers_24_7=None,
        service_count_estimated=None,
        years_in_business_claimed=None,
        is_recruiting=True,   # Only this one
        technician_count_estimated=None,
        serves_commercial=None,
    )
    assert qualifies_for_council(thin) is False


def test_count_populated_signals_counts_non_null():
    company = make_company(is_recruiting=None, technician_count_estimated=None)
    assert count_populated_signals(company) == 5  # 7 total - 2 None = 5


def test_count_populated_signals_counts_false_as_populated():
    # False is a valid signal (we know it's NOT happening); None means we don't know
    company = make_company(is_recruiting=False)
    assert count_populated_signals(company) == 7  # all 7 present (False counts)


def test_custom_threshold_override():
    # Default threshold is 60; pass a lower one
    low_scorer = make_company(conviction_score=45)
    assert qualifies_for_council(low_scorer, min_conviction=40) is True
    assert qualifies_for_council(low_scorer, min_conviction=60) is False
```

### Step 2: Run tests to verify they fail

```bash
py -m pytest tests/test_council_gate.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'agents.council_gate'`

### Step 3: Implement council_gate.py

Create `backend/agents/council_gate.py`:

```python
"""
Council Qualification Gate.

Hard guardrail that prevents the LLM Council from running on companies
with thin data briefs — which would cause hallucination and waste API credits.

ALL criteria must pass for a company to qualify.
"""
from config import settings

CONTENT_SIGNAL_KEYS = [
    "is_family_owned_likely",
    "offers_24_7",
    "service_count_estimated",
    "years_in_business_claimed",
    "is_recruiting",
    "technician_count_estimated",
    "serves_commercial",
]


def count_populated_signals(company: dict) -> int:
    """Count content signal fields that are not None (False counts as populated)."""
    return sum(
        1 for key in CONTENT_SIGNAL_KEYS
        if company.get(key) is not None
    )


def qualifies_for_council(
    company: dict,
    min_conviction: int = None,
    min_signals: int = None,
) -> bool:
    """
    Return True only if ALL qualification criteria are met.

    Args:
        company: Company dict with all scoring and enrichment fields.
        min_conviction: Override settings.council_min_conviction if provided.
        min_signals: Override settings.council_min_signals if provided.

    Returns:
        True if company should proceed to council analysis.
    """
    threshold = min_conviction if min_conviction is not None else settings.council_min_conviction
    sig_min = min_signals if min_signals is not None else settings.council_min_signals

    # Gate 1: Conviction score threshold
    if (company.get("conviction_score") or 0) < threshold:
        return False

    # Gate 2: Must have an active website (council needs real-world context)
    if not company.get("website_active"):
        return False

    # Gate 3: Content enrichment must have run
    if not company.get("content_enriched"):
        return False

    # Gate 4: Must not have been analyzed already (avoid re-burning API credits)
    if company.get("council_analyzed"):
        return False

    # Gate 5: Minimum populated content signals (prevents thin briefs)
    if count_populated_signals(company) < sig_min:
        return False

    return True
```

### Step 4: Run tests to verify they pass

```bash
py -m pytest tests/test_council_gate.py -v
```

Expected: all 9 tests pass.

### Step 5: Commit

```bash
git add backend/agents/council_gate.py backend/tests/test_council_gate.py
git commit -m "feat: council qualification gate — cost/quality guardrail before LLM deliberation"
```

---

## Task 7: LLM Council Agent

**Files:**
- Create: `backend/agents/council.py`
- Create: `backend/tests/test_council.py`

### Step 1: Write the failing tests

Create `backend/tests/test_council.py`:

```python
"""Tests for the LLM Council agent."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.council import CouncilAgent, build_company_brief, parse_chairman_output


# ── Unit: brief construction ─────────────────────────────────────────────────

def make_rich_company() -> dict:
    return {
        "id": "abc-123",
        "name": "Desert Air Services",
        "city": "Phoenix",
        "state": "AZ",
        "google_rating": 4.7,
        "google_review_count": 210,
        "domain_age_years": 18.0,
        "conviction_score": 82,
        "transition_score": 35,
        "quality_score": 30,
        "platform_score": 17,
        "is_family_owned_likely": True,
        "offers_24_7": True,
        "years_in_business_claimed": 18,
        "service_count_estimated": 7,
        "is_recruiting": True,
        "technician_count_estimated": 9,
        "serves_commercial": True,
        "score_explanation": {
            "thesisBullets": ["Family-owned 18yr business", "Website offline signal"],
            "keyRisks": ["Owner-operator dependency"],
            "valuationBand": {"low": 900000, "mid": 2200000, "high": 4500000, "multipleRange": "3.5x–5.5x SDE"},
            "recommendedAction": "Legacy succession outreach",
        },
    }


def test_build_brief_contains_company_name():
    brief = build_company_brief(make_rich_company())
    assert "Desert Air Services" in brief


def test_build_brief_contains_conviction_score():
    brief = build_company_brief(make_rich_company())
    assert "82" in brief


def test_build_brief_contains_content_signals():
    brief = build_company_brief(make_rich_company())
    assert "family" in brief.lower()
    assert "24/7" in brief.lower() or "247" in brief.lower()


def test_build_brief_contains_valuation():
    brief = build_company_brief(make_rich_company())
    assert "2.2M" in brief or "2,200,000" in brief or "$2" in brief


def test_build_brief_is_under_600_words():
    brief = build_company_brief(make_rich_company())
    assert len(brief.split()) < 600


# ── Unit: chairman output parsing ────────────────────────────────────────────

SAMPLE_CHAIRMAN_OUTPUT = """
## Investment Thesis

Desert Air Services represents a compelling acquisition opportunity in the Phoenix HVAC market.
The 18-year operating history with confirmed family ownership creates natural succession pressure.

## Key Strengths
- 4.7-star rating with 210 reviews establishes strong local reputation
- Active commercial client base increases ACV potential
- Team of 9 technicians enables day-one operational continuity

## Key Risks
- Owner-operator dependency requires earnout structure
- Seasonal cash flow concentration in summer cooling season

## Valuation Estimate
$1.8M–$3.5M based on 3.5x–5.5x SDE multiple applied to estimated $500K–$650K SDE

## Recommended Action
Initiate owner outreach. Lead with retirement planning and legacy preservation angle.

## Council Consensus
strong buy
"""


def test_parse_chairman_output_extracts_thesis():
    parsed = parse_chairman_output(SAMPLE_CHAIRMAN_OUTPUT)
    assert "Desert Air Services" in parsed["investment_thesis"] or len(parsed["investment_thesis"]) > 50


def test_parse_chairman_output_extracts_strengths():
    parsed = parse_chairman_output(SAMPLE_CHAIRMAN_OUTPUT)
    assert len(parsed["key_strengths"]) >= 2


def test_parse_chairman_output_extracts_risks():
    parsed = parse_chairman_output(SAMPLE_CHAIRMAN_OUTPUT)
    assert len(parsed["key_risks"]) >= 1


def test_parse_chairman_output_extracts_consensus():
    parsed = parse_chairman_output(SAMPLE_CHAIRMAN_OUTPUT)
    assert parsed["council_consensus"] == "strong buy"


def test_parse_chairman_output_extracts_action():
    parsed = parse_chairman_output(SAMPLE_CHAIRMAN_OUTPUT)
    assert "outreach" in parsed["recommended_action"].lower()


# ── Integration: full council run with mocked OpenRouter ─────────────────────

@pytest.mark.asyncio
async def test_analyze_company_returns_structured_thesis():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = SAMPLE_CHAIRMAN_OUTPUT

    with patch("agents.council.AsyncOpenAI") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client_instance

        agent = CouncilAgent(api_key="sk-or-test")
        result = await agent.analyze(make_rich_company())

    assert result["investment_thesis"]
    assert result["council_consensus"] in {"strong buy", "moderate interest", "split", "pass"}
    assert isinstance(result["key_strengths"], list)
    assert isinstance(result["key_risks"], list)
    assert result["recommended_action"]


@pytest.mark.asyncio
async def test_analyze_company_handles_api_failure_gracefully():
    with patch("agents.council.AsyncOpenAI") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenRouter rate limit")
        )
        MockClient.return_value = mock_client_instance

        agent = CouncilAgent(api_key="sk-or-test")
        result = await agent.analyze(make_rich_company())

    # Should return a fallback dict, not raise
    assert result is not None
    assert "investment_thesis" in result
```

### Step 2: Run tests to verify they fail

```bash
py -m pytest tests/test_council.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'agents.council'`

### Step 3: Implement the Council Agent

Create `backend/agents/council.py`:

```python
"""
CouncilAgent — LLM Council deliberation for HVAC acquisition analysis.

Replicates the llm-council 3-stage pattern directly using OpenRouter,
without requiring the llm-council service to be running.

Stage 1: 3 models produce independent investment analyses in parallel.
Stage 2: Each model anonymously reviews the other analyses.
Stage 3: Chairman synthesizes the final investment thesis.
"""
import asyncio
import re
import logging
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)

COUNCIL_MODELS = [
    "anthropic/claude-sonnet-4-5",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5",
]
CHAIRMAN_MODEL = "anthropic/claude-sonnet-4-5"


def build_company_brief(company: dict) -> str:
    """
    Construct a ~400-word investment brief for council deliberation.
    Structured to maximize signal density while staying under token limits.
    """
    exp = company.get("score_explanation") or {}
    vb = exp.get("valuationBand") or {}
    bullets = exp.get("thesisBullets") or []
    risks = exp.get("keyRisks") or []

    # Format content signals
    signals = []
    if company.get("is_family_owned_likely"):
        signals.append("Family-owned business")
    if company.get("years_in_business_claimed"):
        signals.append(f"In operation {company['years_in_business_claimed']} years (stated on website)")
    if company.get("offers_24_7"):
        signals.append("24/7 emergency service advertised")
    if company.get("is_recruiting"):
        signals.append("Actively recruiting technicians")
    if company.get("serves_commercial"):
        signals.append("Serves commercial clients")
    if company.get("technician_count_estimated"):
        signals.append(f"Team of {company['technician_count_estimated']} technicians")
    if company.get("service_count_estimated"):
        signals.append(f"~{company['service_count_estimated']} distinct services offered")
    if not signals:
        signals.append("Limited website data — scoring based on reviews and domain signals")

    # Format valuation
    if vb.get("mid"):
        mid = vb["mid"]
        val_str = f"${mid/1_000_000:.1f}M" if mid >= 1_000_000 else f"${mid/1_000:.0f}K"
        val_range = f"{vb.get('multipleRange', 'N/A')} SDE — est. midpoint {val_str}"
    else:
        val_range = "Not estimated (insufficient data)"

    return f"""ACQUISITION CANDIDATE BRIEF
============================
Company: {company.get('name', 'Unknown')}
Location: {company.get('city', '')}, {company.get('state', '')}
Google Rating: {company.get('google_rating', 'N/A')} ({company.get('google_review_count', 0)} reviews)
Domain Age: {round(company.get('domain_age_years') or 0)}yr
Conviction Score: {company.get('conviction_score', 0)}/100
  — Transition: {company.get('transition_score', 0)}/40
  — Quality: {company.get('quality_score', 0)}/35
  — Platform: {company.get('platform_score', 0)}/25

WEBSITE INTELLIGENCE
{chr(10).join(f"• {s}" for s in signals)}

PRELIMINARY THESIS SIGNALS
{chr(10).join(f"• {b}" for b in bullets[:4]) or "• No thesis generated yet"}

KEY DILIGENCE RISKS
{chr(10).join(f"• {r}" for r in risks[:3]) or "• Owner-operator dependency (standard for this sector)"}

PROXY VALUATION
{val_range}
Comparable HVAC transactions: 3.0x–7.0x SDE (market range)
Residential-focused operators typically 3.5x–5.5x; commercial mix commands premium.

CONTEXT
Target geography: {company.get('state', '')} — {'premium HVAC market' if company.get('state') in {'AZ','TX','FL','TN','NC','GA','SC','NV'} else 'secondary market'}
Discovery source: {company.get('discovery_source', 'unknown')}
"""


def parse_chairman_output(text: str) -> dict:
    """
    Parse structured sections from chairman synthesis markdown.
    Handles both ## headers and plain text fallback.
    """
    def extract_section(pattern: str) -> str:
        match = re.search(
            rf"##?\s*{pattern}\s*\n+(.*?)(?=##?\s|\Z)",
            text, re.S | re.I
        )
        return match.group(1).strip() if match else ""

    def extract_bullets(section_text: str) -> list[str]:
        lines = [l.strip().lstrip("-•*").strip() for l in section_text.split("\n")]
        return [l for l in lines if len(l) > 10]

    # Investment thesis — first substantial paragraph
    thesis_section = extract_section("investment thesis")
    if not thesis_section:
        # Fallback: first non-header paragraph > 50 chars
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.startswith("#")]
        thesis_section = next((p for p in paragraphs if len(p) > 50), text[:500])

    # Consensus
    consensus_match = re.search(
        r"(?:council consensus|consensus)[:\s]*(strong buy|moderate interest|split|pass)",
        text, re.I
    )
    consensus = consensus_match.group(1).lower() if consensus_match else "moderate interest"

    # Recommended action
    action_section = extract_section("recommended action")
    action = action_section.split("\n")[0].strip() if action_section else "Monitor — gather additional data"

    # Valuation estimate
    val_match = re.search(r"\$[\d,\.]+[MK]?\s*[–—-]\s*\$[\d,\.]+[MK]?", text)
    val_estimate = val_match.group(0) if val_match else "See valuation tab for proxy estimate"

    return {
        "investment_thesis": thesis_section[:1000],
        "key_strengths": extract_bullets(extract_section("key strengths")),
        "key_risks": extract_bullets(extract_section("key risks")),
        "valuation_estimate": val_estimate,
        "recommended_action": action[:200],
        "council_consensus": consensus,
    }


STAGE1_PROMPT = """You are a private equity analyst evaluating an HVAC acquisition target.
Based on the brief below, provide your independent investment analysis.

{brief}

Provide:
1. Your investment recommendation: STRONG BUY / MODERATE INTEREST / PASS
2. Top 3 reasons supporting your recommendation
3. Top 2 risks an acquirer must diligence
4. Your valuation range estimate
Be specific. Cite specific signals from the brief. Max 300 words."""

STAGE2_PROMPT = """You are reviewing investment analyses of the same HVAC acquisition target.
Original brief: {brief}

Three analysts produced these assessments (anonymized):
{responses}

Rank these responses A, B, C by quality of reasoning and specificity.
Format exactly:
FINAL RANKING:
1. Response [X]
2. Response [Y]
3. Response [Z]

Briefly (1-2 sentences) explain your top choice."""

CHAIRMAN_PROMPT = """You are the chairman of an investment committee reviewing an HVAC acquisition opportunity.
Three analysts evaluated this target and peer-reviewed each other's work.

COMPANY BRIEF:
{brief}

ANALYST ASSESSMENTS:
{stage1_responses}

PEER RANKINGS (aggregate — lower rank = stronger analysis):
{rankings}

Synthesize a final investment thesis. Structure your response with these exact headings:
## Investment Thesis
## Key Strengths
## Key Risks
## Valuation Estimate
## Recommended Action
## Council Consensus
(one of: strong buy / moderate interest / split / pass)

Write as if presenting to a PE investment committee. Be specific, cite evidence, acknowledge uncertainty. Max 500 words."""


class CouncilAgent:
    """
    3-stage LLM Council deliberation for HVAC acquisition analysis.
    Uses OpenRouter to query multiple models in parallel.
    """

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.models = settings.council_models or COUNCIL_MODELS
        self.chairman = settings.council_chairman or CHAIRMAN_MODEL

    async def _query_model(self, model: str, prompt: str, max_tokens: int = 500) -> str:
        """Query a single model and return response text."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Council model {model} failed: {e}")
            return f"[{model} unavailable]"

    async def _stage1(self, brief: str) -> list[dict]:
        """Stage 1: All models produce independent analyses in parallel."""
        prompt = STAGE1_PROMPT.format(brief=brief)
        responses = await asyncio.gather(
            *[self._query_model(m, prompt, 400) for m in self.models]
        )
        return [
            {"model": model, "response": resp, "label": f"Response {chr(65 + i)}"}
            for i, (model, resp) in enumerate(zip(self.models, responses))
        ]

    async def _stage2(self, brief: str, stage1: list[dict]) -> list[dict]:
        """Stage 2: Each model anonymously reviews the other analyses."""
        anon_responses = "\n\n".join(
            f"--- {r['label']} ---\n{r['response']}" for r in stage1
        )
        prompt = STAGE2_PROMPT.format(brief=brief, responses=anon_responses)
        reviews = await asyncio.gather(
            *[self._query_model(m, prompt, 200) for m in self.models]
        )
        return [
            {"model": model, "review": review}
            for model, review in zip(self.models, reviews)
        ]

    async def _stage3(self, brief: str, stage1: list[dict], stage2: list[dict]) -> str:
        """Stage 3: Chairman synthesizes final thesis from all inputs."""
        formatted_s1 = "\n\n".join(
            f"Analyst {r['label']} ({r['model']}):\n{r['response']}" for r in stage1
        )
        formatted_s2 = "\n\n".join(
            f"Reviewer {r['model']}:\n{r['review']}" for r in stage2
        )
        prompt = CHAIRMAN_PROMPT.format(
            brief=brief,
            stage1_responses=formatted_s1,
            rankings=formatted_s2,
        )
        return await self._query_model(self.chairman, prompt, 700)

    async def analyze(self, company: dict) -> dict:
        """
        Run full 3-stage deliberation for a single company.
        Returns structured investment thesis dict.
        Falls back to a minimal dict on complete failure.
        """
        fallback = {
            "investment_thesis": "Council analysis unavailable — see preliminary scoring for context.",
            "key_strengths": [],
            "key_risks": [],
            "valuation_estimate": "See valuation tab",
            "recommended_action": "Monitor — run council when API keys configured",
            "council_consensus": "pass",
        }

        try:
            brief = build_company_brief(company)
            stage1 = await self._stage1(brief)
            stage2 = await self._stage2(brief, stage1)
            chairman_output = await self._stage3(brief, stage1, stage2)
            return parse_chairman_output(chairman_output)
        except Exception as e:
            logger.error(f"Council analysis failed for {company.get('name')}: {e}")
            return fallback

    async def analyze_batch(
        self,
        companies: list[dict],
        progress_callback=None,
    ) -> list[tuple[str, dict]]:
        """
        Analyze multiple companies concurrently (bounded concurrency to
        respect OpenRouter rate limits). Returns list of (company_id, thesis) tuples.
        """
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent council runs

        async def analyze_with_sem(company):
            async with semaphore:
                result = await self.analyze(company)
                if progress_callback:
                    await progress_callback(f"Council reviewed: {company.get('name')}", 0)
                return (company["id"], result)

        return await asyncio.gather(*[analyze_with_sem(c) for c in companies])
```

### Step 4: Run tests to verify they pass

```bash
py -m pytest tests/test_council.py -v
```

Expected: all 12 tests pass.

If `test_parse_chairman_output_extracts_thesis` fails: the thesis extraction regex may not match. The fallback in `parse_chairman_output` takes the first long paragraph — check that `SAMPLE_CHAIRMAN_OUTPUT` has a paragraph > 50 chars after the `## Investment Thesis` header.

### Step 5: Commit

```bash
git add backend/agents/council.py backend/tests/test_council.py
git commit -m "feat: LLM Council agent — 3-stage OpenRouter deliberation for investment thesis"
```

---

## Task 8: Orchestrator Integration

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Create: `backend/tests/test_orchestrator_stages.py`

### Step 1: Write the failing test

Create `backend/tests/test_orchestrator_stages.py`:

```python
"""Smoke test: orchestrator stages complete without error in mock mode."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.orchestrator import PipelineOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_runs_all_stages_in_mock_mode():
    """Full pipeline smoke test — mock mode, no real API calls."""
    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(websocket=ws_mock)

    with patch("agents.orchestrator.AsyncSessionLocal") as MockSession:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        MockSession.return_value = mock_db

        # Should not raise
        try:
            await asyncio.wait_for(
                orchestrator.run(
                    cities=[("Phoenix", "AZ")],
                    max_companies=5,
                    generate_dossiers_for_top=0,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            pytest.fail("Orchestrator timed out after 30s in mock mode")
        except Exception as e:
            # DB errors are expected in full mock — just verify it ran stages
            assert "stage" not in str(e).lower(), f"Unexpected error: {e}"
```

### Step 2: Modify orchestrator.py — Add new stages

Open `backend/agents/orchestrator.py`. You need to add three things:

**A. Import the new agents at the top of the file** (after existing imports):

```python
from agents.content_enrichment import ContentEnrichmentAgent
from agents.council import CouncilAgent
from agents.council_gate import qualifies_for_council
from config import settings
```

**B. In the `run()` method, add STAGE 2.5 (ContentEnrichment) after the existing enrichment stage.**

Find the line that broadcasts `"Enriched {len} companies"` (around line 157 in current file). After the `await db.commit()` for the enrichment stage, add:

```python
            # ─── STAGE 2.5: Content Enrichment ──────────────────────────
            await self._broadcast("content_enrich", "Extracting website content signals…", 0.42)
            if settings.firecrawl_api_key:
                content_agent = ContentEnrichmentAgent(api_key=settings.firecrawl_api_key)
                companies_content = await content_agent.enrich_batch(
                    companies_enriched,
                    progress_callback=lambda m, p: self._broadcast("content_enrich", m, 0.42 + p * 0.10),
                )
            else:
                # Mock mode: set content_enriched=False on all companies
                for c in companies_enriched:
                    c["content_enriched"] = False
                companies_content = companies_enriched
                logger.info("Content enrichment skipped — no FIRECRAWL_API_KEY")

            async with AsyncSessionLocal() as db:
                for c in companies_content:
                    await db.execute(
                        update(Company).where(Company.id == c.get("id")).values(
                            is_family_owned_likely=c.get("is_family_owned_likely"),
                            offers_24_7=c.get("offers_24_7"),
                            service_count_estimated=c.get("service_count_estimated"),
                            years_in_business_claimed=c.get("years_in_business_claimed"),
                            is_recruiting=c.get("is_recruiting"),
                            technician_count_estimated=c.get("technician_count_estimated"),
                            serves_commercial=c.get("serves_commercial"),
                            content_enriched=c.get("content_enriched", False),
                        )
                    )
                await db.commit()

            await self._broadcast("content_enrich", f"Content signals extracted for {len(companies_content)} companies", 0.52)
```

**C. Add STAGE 7 (Council) after the ranking stage** (after the `await db.commit()` for ranking, before the dossier stage). The ranking stage DB commit is around line 187:

```python
            # ─── STAGE 7: Council Analysis ──────────────────────────────
            await self._broadcast("council", "Qualifying candidates for council review…", 0.76)

            if settings.openrouter_api_key:
                # Select top-10 candidates that pass the qualification gate
                qualified = [
                    c for c in companies_ranked
                    if qualifies_for_council(c)
                ][:10]

                if qualified:
                    await self._broadcast(
                        "council",
                        f"LLM Council reviewing {len(qualified)} top candidates…",
                        0.77,
                    )
                    council_agent = CouncilAgent(api_key=settings.openrouter_api_key)
                    council_results = await council_agent.analyze_batch(
                        qualified,
                        progress_callback=lambda m, p: self._broadcast("council", m, 0.77 + p * 0.15),
                    )

                    # Store council theses as memos (version 2, model_used="council-v1")
                    async with AsyncSessionLocal() as db:
                        from models import Memo
                        from datetime import datetime
                        for company_id, thesis in council_results:
                            content_md = _format_council_thesis_markdown(thesis)
                            existing = (await db.execute(
                                select(Memo).where(
                                    Memo.company_id == company_id,
                                    Memo.model_used == "council-v1",
                                )
                            )).scalar_one_or_none()
                            if existing:
                                existing.content = content_md
                                existing.updated_at = datetime.utcnow()
                            else:
                                db.add(Memo(
                                    company_id=company_id,
                                    version=2,
                                    title=f"Council Investment Thesis",
                                    content=content_md,
                                    status="final",
                                    model_used="council-v1",
                                    generated_at=datetime.utcnow(),
                                ))
                            await db.execute(
                                update(Company).where(Company.id == company_id).values(
                                    council_analyzed=True,
                                )
                            )
                        await db.commit()
                    await self._broadcast("council", f"Council analysis complete for {len(qualified)} companies", 0.92)
                else:
                    await self._broadcast("council", "No candidates qualified for council review (low scores or thin data)", 0.92)
            else:
                logger.info("Council stage skipped — no OPENROUTER_API_KEY")
                await self._broadcast("council", "Council stage skipped (configure OPENROUTER_API_KEY to enable)", 0.92)
```

**D. Add the markdown formatter helper function** at module level (outside the class, before or after the class):

```python
def _format_council_thesis_markdown(thesis: dict) -> str:
    """Format council thesis dict as readable markdown for the memo viewer."""
    consensus_colors = {
        "strong buy": "🟢",
        "moderate interest": "🟡",
        "split": "🟠",
        "pass": "🔴",
    }
    icon = consensus_colors.get(thesis.get("council_consensus", ""), "⚖️")
    strengths = "\n".join(f"- {s}" for s in thesis.get("key_strengths", []))
    risks = "\n".join(f"- {r}" for r in thesis.get("key_risks", []))

    return f"""# Council Investment Thesis
{icon} **Council Consensus:** {thesis.get('council_consensus', 'N/A').title()}

## Investment Thesis
{thesis.get('investment_thesis', '')}

## Key Strengths
{strengths or '- Analysis in progress'}

## Key Risks
{risks or '- Standard HVAC sector risks apply'}

## Valuation Estimate
{thesis.get('valuation_estimate', 'See valuation tab for proxy estimate')}

## Recommended Action
**{thesis.get('recommended_action', 'Monitor')}**

---
*Generated by LLM Council — 3-model deliberation (Stage 1: independent analysis, Stage 2: peer review, Stage 3: chairman synthesis)*
"""
```

**E. Update progress percentages for existing stages** to make room. The existing stages use 0.0–0.75. Adjust so:
- Scout: 0.0–0.18
- Enrich: 0.18–0.40
- Content: 0.40–0.52
- Signals: 0.52–0.58
- Score: 0.58–0.65
- Rank: 0.65–0.76
- Council: 0.76–0.92
- Dossiers: 0.92–0.97
- Complete: 0.97–1.0

**F. Update the Scout stage to use FirecrawlScout when key is present.** Find the Scout section (Stage 1, around line 75–120). After `await self._broadcast("scout", ...)`:

```python
            # ─── STAGE 1: Scout ──────────────────────────────────────────
            await self._broadcast("scout", "Discovering HVAC companies…", 0.0)
            if settings.firecrawl_api_key and not settings.use_mock_data:
                from agents.firecrawl_scout import FirecrawlScout
                scout = FirecrawlScout(api_key=settings.firecrawl_api_key)
                companies_raw = await scout.run_batch(cities, max_per_city=max_companies // len(cities) if cities else 30)
                logger.info(f"FirecrawlScout discovered {len(companies_raw)} companies")
            else:
                # Existing mock scout — no change needed
                companies_raw = await scout_agent.run_batch(cities, max_per_city=...)
```

The exact implementation depends on how the Scout is called today (lines 75–120). Check the current code and wrap the existing `Scout` call in an `else` branch. The `FirecrawlScout` call wraps in `if settings.firecrawl_api_key and not settings.use_mock_data`.

### Step 3: Run the smoke test

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m pytest tests/test_orchestrator_stages.py -v
```

Expected: 1 test passes (or raises only a DB-related error, not a stage logic error).

### Step 4: Manual integration test

With the backend running, trigger a short pipeline run via curl:

```bash
curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d "{\"city\": \"Phoenix\", \"state\": \"AZ\", \"max_results\": 5}"
```

Watch the backend logs. Verify:
- Stage `scout` appears
- Stage `content_enrich` appears (logs "skipped" if no FIRECRAWL_API_KEY)
- Stage `council` appears (logs "skipped" if no OPENROUTER_API_KEY)
- Stage `complete` appears

### Step 5: Commit

```bash
git add backend/agents/orchestrator.py backend/tests/test_orchestrator_stages.py
git commit -m "feat: orchestrator — add ContentEnrich stage + Council stage with qualification gate"
```

---

## Task 9: Frontend — Types and Council Thesis Display

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/DealDesk.tsx`
- Modify: `frontend/src/api/client.ts`

### Step 1: Update types/index.ts

In the `Company` interface, add after the existing enrichment fields (after `websiteOutdated`):

```typescript
  // Content enrichment signals
  isFamilyOwnedLikely?: boolean | null;
  offers247?: boolean | null;
  serviceCountEstimated?: number | null;
  yearsInBusinessClaimed?: number | null;
  isRecruiting?: boolean | null;
  technicianCountEstimated?: number | null;
  servesCommercial?: boolean | null;
  discoverySource?: string | null;
  contentEnriched?: boolean;
  councilAnalyzed?: boolean;
```

### Step 2: Update dealdesk serializer to pass new fields

In `backend/routers/dealdesk.py`, find the `company_to_deal()` function. Add the new fields to the returned dict:

```python
    # Content enrichment fields
    "isFamilyOwnedLikely": c.is_family_owned_likely,
    "offers247": c.offers_24_7,
    "serviceCountEstimated": c.service_count_estimated,
    "yearsInBusinessClaimed": c.years_in_business_claimed,
    "isRecruiting": c.is_recruiting,
    "technicianCountEstimated": c.technician_count_estimated,
    "servesCommercial": c.serves_commercial,
    "discoverySource": c.discovery_source,
    "contentEnriched": c.content_enriched or False,
    "councilAnalyzed": c.council_analyzed or False,
```

### Step 3: Update the tearsheet endpoint to include council memo

In `backend/routers/dealdesk.py`, the tearsheet endpoint fetches memos. Verify it includes `council-v1` memos. In the tearsheet response, memos are already included via the `memos` list. The `MemoViewer` in the frontend shows the first memo — update the selector to prefer `council-v1`.

In the tearsheet response construction, ensure memos are sorted: council memos (`model_used == "council-v1"`) first:

```python
    # Sort memos: council-v1 first, then by created_at desc
    memos_sorted = sorted(
        memos,
        key=lambda m: (0 if getattr(m, "model_used", "") == "council-v1" else 1, -(getattr(m, "generated_at") or datetime.min).timestamp()),
    )
```

### Step 4: Update DealDesk.tsx — Council thesis display

In `frontend/src/pages/DealDesk.tsx`, update the **Thesis tab** in `DecisionPane` to show council analysis badge when available.

Find the thesis tab content (the `{activeTab === "thesis" && ...}` block). Add a council badge above the "RECOMMENDED ACTION" card:

```tsx
{activeTab === "thesis" && (
  <div className="space-y-5">
    {/* Council consensus badge — shown when council has analyzed */}
    {(activeDeal as any)?.councilAnalyzed && (
      <div className="glass-card p-3 border-accent/30 bg-accent/5">
        <div className="flex items-center gap-2">
          <span className="text-accent text-xs font-mono font-semibold">⚖ COUNCIL ANALYSIS</span>
          <span className="text-xs text-slate-500 ml-auto font-mono">3-model deliberation complete</span>
        </div>
        <p className="text-xs text-slate-400 mt-1">View the full council investment thesis in the Memo tab.</p>
      </div>
    )}
    {/* ... existing thesis content ... */}
```

Also update the **Memo tab** in `DecisionPane` to show a `COUNCIL THESIS` label when the memo is from the council:

```tsx
{activeTab === "memo" && (
  <div>
    <div className="flex items-center justify-between mb-3">
      <div className="terminal-label text-[10px] flex items-center gap-2">
        INVESTMENT MEMO
        {(tearsheet as any)?.memos?.[0]?.modelUsed === "council-v1" && (
          <span className="text-accent text-[10px] font-mono">⚖ COUNCIL</span>
        )}
      </div>
      ...
```

### Step 5: DealDesk language cleanup

In `DealDesk.tsx`, make these text replacements:

| Find | Replace |
|------|---------|
| `DEAL SCREENER` | `DEAL FILTER` |
| `MATCHING TARGETS` | `TARGETS` |
| `{total} targets ranked` | `{total} ranked · {councilCount} council-reviewed` |

Add `councilCount` to the DealDesk component state by deriving it from the deals array:

```tsx
const councilCount = deals.filter((d: any) => d.councilAnalyzed).length
```

### Step 6: Add discovery source badge to DealFeedItem

In `DealFeedItem`, after the `WorkflowBadge`, add:

```tsx
{(deal as any).councilAnalyzed && (
  <span className="text-[10px] font-mono text-accent/70">⚖</span>
)}
{(deal as any).discoverySource === "firecrawl_search" && (
  <span className="text-[10px] font-mono text-slate-600">live</span>
)}
```

### Step 7: Verify frontend compiles

```bash
cd C:\Users\joonk\hvac-intelligence\frontend
npm run build 2>&1 | tail -20
```

Expected: `built in X.XXs` with no TypeScript errors.

If TypeScript errors appear about `councilAnalyzed` or `isFamilyOwnedLikely`: add the fields to the `Company` interface in `types/index.ts` (already done in Step 1 — check that they're present).

### Step 8: Commit

```bash
git add frontend/src/types/index.ts frontend/src/pages/DealDesk.tsx backend/routers/dealdesk.py
git commit -m "feat: frontend council thesis display, discovery source badges, language cleanup"
```

---

## Task 10: End-to-End Validation

### Step 1: Start backend

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Verify startup:
```
Database ready (schema migrated).
Comp deals seeded.
```

### Step 2: Verify new columns exist in running DB

```bash
curl -s http://localhost:8000/api/health
```

Expected: `{"status":"ok","version":"2.0.0",...}`

### Step 3: Run a mock pipeline and verify new stages appear

```bash
curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d "{\"max_results\": 10}"
```

Watch backend stdout. You should see these log lines within 30 seconds:

```
Broadcasting: stage=scout ...
Broadcasting: stage=content_enrich ... Content enrichment skipped
Broadcasting: stage=council ... Council stage skipped
Broadcasting: stage=complete
```

### Step 4: Run all backend tests

```bash
cd C:\Users\joonk\hvac-intelligence\backend
py -m pytest tests/ -v --tb=short
```

Expected: all tests pass. If any fail, fix before marking complete.

### Step 5: Verify frontend loads council fields

Start frontend and open browser DevTools Network tab:

```bash
cd C:\Users\joonk\hvac-intelligence\frontend
npm run dev
```

Navigate to `http://localhost:5173`. Open a company in the deal feed. In the Network tab, find the `/api/dealdesk/tearsheet/{id}` response and verify it contains:
- `"councilAnalyzed": false` (false because mock mode)
- `"contentEnriched": false`
- `"discoverySource": "mock"`

### Step 6: Final commit

```bash
cd C:\Users\joonk\hvac-intelligence
git add -A
git commit -m "feat: complete real-data intelligence stack — FirecrawlScout, ContentEnrichment, LLM Council, scoring enhancements, terminal language cleanup"
```

---

## Enabling Live Mode (After All Tasks Complete)

To switch from mock to real data, add your API keys to `backend/.env`:

```env
USE_MOCK_DATA=false
FIRECRAWL_API_KEY=fc-your-actual-key
OPENROUTER_API_KEY=sk-or-your-actual-key
```

Restart backend. Run pipeline. The system will:
1. Discover real HVAC companies via Firecrawl + Yellow Pages
2. Visit their actual websites to extract content signals
3. Score them with the enhanced model
4. Qualify top-10 for council (conviction ≥ 60, content_enriched=True, ≥ 4 signals)
5. Run 3-stage LLM deliberation on qualifying candidates
6. Display the council thesis in the right panel

Expected first run time: 5–15 minutes for 50 companies depending on Firecrawl API speed and whether council is triggered.

---

## Appendix: Test Run Commands

```bash
# Individual task tests
py -m pytest tests/test_firecrawl_scout.py -v
py -m pytest tests/test_content_enrichment.py -v
py -m pytest tests/test_scoring_engine_content.py -v
py -m pytest tests/test_council_gate.py -v
py -m pytest tests/test_council.py -v

# All tests
py -m pytest tests/ -v --tb=short

# Single test by name
py -m pytest tests/test_council_gate.py::test_disqualified_below_conviction_threshold -v
```
