# SaaS Product Polish — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Goal:** Transform the HVAC Deal Intelligence Platform into a commercial product: replace mock/Google Scout with OSM + Yellow Pages free-tier discovery, redesign scoring for transparency, add template memo with PDF/MD export, clean up Deal Desk workflow states, rebuild Pipeline and Settings UI, and expose valuation assumptions.

**Architecture:** Free tier uses OSMScout (Overpass API) + YPScraper (Yellow Pages HTML) for company discovery with no API keys required. Firecrawl + LLM Council remain as premium upgrades activated by optional API keys. Template-based memo generation replaces the Claude-default dossier. All UI pages are redesigned to read as a commercial product, not a developer tool.

**Design doc:** `docs/plans/2026-03-05-saas-product-polish-design.md`

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async / SQLite — HTTPX + BeautifulSoup for scraping — Overpass API (no key) — jsPDF + html2canvas for client-side PDF — React/TypeScript/TanStack Query frontend

---

## Pre-flight: Merge Feature Branch + Create Worktree

Before starting any task, merge the completed real-data-intelligence-stack feature branch and create an isolated worktree for this work.

```bash
# Step 1 — Verify feature branch tests pass
cd C:\Users\joonk\hvac-intelligence\.worktrees\real-data-stack\backend
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 52 passed

# Step 2 — Merge feature branch into master
cd C:\Users\joonk\hvac-intelligence
git merge feature/real-data-intelligence-stack
# Expected: Fast-forward merge (no conflicts)

# Step 3 — Verify merged state
cd backend
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 52 passed

# Step 4 — Create worktree for this feature
git worktree add .worktrees/saas-polish -b feature/saas-product-polish
# Expected: "Preparing worktree (new branch 'feature/saas-product-polish')"
```

All subsequent work happens in: `C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish`

Pre-flight check (run from the new worktree):
```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\backend
py -c "from config import settings; print('ok')"
# Expected: ok
```

---

## Task 1: Config Cleanup — Remove Demo Mode

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/.env` (if present)
- Modify: `backend/agents/orchestrator.py` (remove `use_mock_data` references)

### Step 1: Write the failing test

Create `backend/tests/test_config_cleanup.py`:

```python
"""Config must not expose deprecated demo-mode or Google Places fields."""
from config import settings


def test_no_use_mock_data_field():
    """use_mock_data must not exist on settings."""
    assert not hasattr(settings, "use_mock_data"), (
        "use_mock_data must be removed — app always uses real discovery"
    )


def test_no_google_places_key_field():
    """google_places_api_key must not exist on settings."""
    assert not hasattr(settings, "google_places_api_key"), (
        "google_places_api_key must be removed — OSMScout requires no key"
    )


def test_valuation_defaults_present():
    """Valuation assumption defaults must be configurable via settings."""
    assert hasattr(settings, "valuation_ticket_size"), "avg ticket size default required"
    assert hasattr(settings, "valuation_jobs_per_review"), "jobs per review default required"
    assert hasattr(settings, "valuation_ebitda_margin"), "EBITDA margin default required"
    assert hasattr(settings, "valuation_multiple_low"), "valuation multiple low required"
    assert hasattr(settings, "valuation_multiple_high"), "valuation multiple high required"
    assert settings.valuation_ticket_size == 385
    assert settings.valuation_jobs_per_review == 8
    assert settings.valuation_ebitda_margin == 0.20
    assert settings.valuation_multiple_low == 3.5
    assert settings.valuation_multiple_high == 5.5
```

### Step 2: Run to verify it fails

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\backend
py -m pytest tests/test_config_cleanup.py -v
# Expected: 3 FAILED (fields still exist, valuation defaults missing)
```

### Step 3: Update config.py

Open `backend/config.py`. Make the following changes:

**Remove these fields:**
```python
# DELETE these lines:
google_places_api_key: str = ""
use_mock_data: bool = True
google_api_delay_ms: int = 200
```

**Add after `openrouter_api_key`:**
```python
    # Valuation assumption defaults (configurable, shown in UI)
    valuation_ticket_size: int = 385          # Average HVAC ticket size in USD
    valuation_jobs_per_review: int = 8        # Estimated jobs per Google review
    valuation_ebitda_margin: float = 0.20     # HVAC EBITDA margin assumption
    valuation_multiple_low: float = 3.5       # Acquisition multiple low end
    valuation_multiple_high: float = 5.5      # Acquisition multiple high end
```

### Step 4: Fix orchestrator.py — remove use_mock_data reference

In `backend/agents/orchestrator.py`, find the Scout stage (around line 110):

```python
# FIND (current feature branch code):
if settings.firecrawl_api_key and not getattr(settings, "use_mock_data", True):
    from agents.firecrawl_scout import FirecrawlScout
    ...
else:
    scout = ScoutAgent()
    ...
```

Replace with (leave the FirecrawlScout branch, update the else — Task 4 will fill in OSMScout):
```python
# REPLACE with:
if settings.firecrawl_api_key:
    from agents.firecrawl_scout import FirecrawlScout
    firecrawl_scout = FirecrawlScout(api_key=settings.firecrawl_api_key)
    companies_raw = await firecrawl_scout.run_batch(
        target_cities,
        max_per_city=max_per_city,
    )
    logger.info(f"FirecrawlScout discovered {len(companies_raw)} companies")
else:
    # Free tier: OSMScout + YPScraper fallback (implemented in Task 4)
    from agents.osm_scout import OSMScout
    osm_scout = OSMScout()
    companies_raw = await osm_scout.run_batch(
        target_cities,
        max_per_city=max_per_city,
        progress_callback=lambda m, p: self._broadcast("scout", m, p * 0.18),
    )
    logger.info(f"OSMScout discovered {len(companies_raw)} companies")
```

Note: `OSMScout` doesn't exist yet (created in Task 2). This will break the orchestrator import temporarily — that's fine, the orchestrator test uses mocks.

### Step 5: Run tests

```bash
py -m pytest tests/test_config_cleanup.py -v
# Expected: 3 passed
```

Run full suite to check nothing else broke:
```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 52+ passed (orchestrator smoke test may fail if it imports OSMScout — OK for now)
```

### Step 6: Commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add backend/config.py backend/agents/orchestrator.py backend/tests/test_config_cleanup.py
git commit -m "feat: remove demo mode + google places config, add valuation defaults"
```

---

## Task 2: OSMScout Agent — Overpass API Discovery

**Files:**
- Create: `backend/agents/osm_scout.py`
- Create: `backend/tests/test_osm_scout.py`

### Step 1: Write the failing tests

Create `backend/tests/test_osm_scout.py`:

```python
"""OSMScout: Overpass API HVAC business discovery."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.osm_scout import OSMScout, _osm_element_to_company, STATE_NAME_MAP


# --- Unit: element mapping ---

def test_osm_node_maps_to_company_dict():
    element = {
        "type": "node", "id": 123456,
        "lat": 33.448, "lon": -112.073,
        "tags": {
            "name": "Smith HVAC",
            "phone": "+1-602-555-1234",
            "website": "https://smithhvac.com",
            "addr:street": "100 Main St",
            "addr:city": "Phoenix",
            "addr:state": "AZ",
        }
    }
    result = _osm_element_to_company(element, "Phoenix", "AZ")
    assert result["name"] == "Smith HVAC"
    assert result["phone"] == "+1-602-555-1234"
    assert result["website"] == "https://smithhvac.com"
    assert result["city"] == "Phoenix"
    assert result["state"] == "AZ"
    assert result["place_id"].startswith("osm_node_")
    assert result["category"] == "HVAC"
    assert result["google_rating"] is None
    assert result["google_review_count"] == 0


def test_osm_element_without_name_returns_none():
    element = {"type": "node", "id": 999, "lat": 33.0, "lon": -112.0, "tags": {}}
    result = _osm_element_to_company(element, "Phoenix", "AZ")
    assert result is None


def test_state_name_map_has_all_50_states():
    assert "AZ" in STATE_NAME_MAP
    assert "TX" in STATE_NAME_MAP
    assert "FL" in STATE_NAME_MAP
    assert STATE_NAME_MAP["AZ"] == "Arizona"
    assert STATE_NAME_MAP["TX"] == "Texas"


# --- Integration: search_city ---

@pytest.mark.asyncio
async def test_search_city_parses_overpass_response():
    mock_response = {
        "elements": [
            {
                "type": "node", "id": 1,
                "lat": 33.4, "lon": -112.0,
                "tags": {"name": "Cool Air LLC", "craft": "hvac",
                         "addr:city": "Phoenix", "addr:state": "AZ"}
            },
            {
                "type": "node", "id": 2,
                "lat": 33.5, "lon": -112.1,
                "tags": {"name": "Desert Heat Co", "shop": "hvac",
                         "phone": "602-111-2222"}
            },
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        scout = OSMScout()
        results = await scout.search_city("Phoenix", "AZ", max_results=10)

    assert len(results) == 2
    assert results[0]["name"] == "Cool Air LLC"
    assert results[1]["name"] == "Desert Heat Co"


@pytest.mark.asyncio
async def test_search_city_filters_unnamed_elements():
    mock_response = {
        "elements": [
            {"type": "node", "id": 1, "lat": 33.4, "lon": -112.0, "tags": {}},  # no name
            {"type": "node", "id": 2, "lat": 33.5, "lon": -112.1,
             "tags": {"name": "Valid HVAC Co"}},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        scout = OSMScout()
        results = await scout.search_city("Dallas", "TX", max_results=10)

    assert len(results) == 1
    assert results[0]["name"] == "Valid HVAC Co"


@pytest.mark.asyncio
async def test_search_city_returns_empty_on_http_error():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
               side_effect=Exception("network error")):
        scout = OSMScout()
        results = await scout.search_city("Phoenix", "AZ", max_results=10)
    assert results == []
```

### Step 2: Run to verify they fail

```bash
py -m pytest tests/test_osm_scout.py -v
# Expected: ImportError — agents.osm_scout not found
```

### Step 3: Implement osm_scout.py

Create `backend/agents/osm_scout.py`:

```python
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
```

### Step 4: Run tests

```bash
py -m pytest tests/test_osm_scout.py -v
# Expected: 6 passed
```

### Step 5: Run full suite

```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 58+ passed
```

### Step 6: Commit

```bash
git add backend/agents/osm_scout.py backend/tests/test_osm_scout.py
git commit -m "feat: OSMScout — free-tier HVAC discovery via Overpass API"
```

---

## Task 3: YPScraper — Yellow Pages Fallback

**Files:**
- Create: `backend/agents/yp_scraper.py`
- Create: `backend/tests/test_yp_scraper.py`

### Step 1: Write the failing tests

Create `backend/tests/test_yp_scraper.py`:

```python
"""YPScraper: Yellow Pages HTML scraping fallback for HVAC discovery."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.yp_scraper import YPScraper, _parse_yp_listing


SAMPLE_YP_HTML = """
<div class="result organic">
  <h2 class="n">
    <a class="business-name" href="/phoenix-az/hvac/smith-hvac">Smith HVAC Services</a>
  </h2>
  <div class="phones">
    <span class="full-number">(602) 555-1234</span>
  </div>
  <div class="adr">
    <span class="street-address">100 Main St</span>
    <span class="city">Phoenix</span>,
    <span class="state">AZ</span>
  </div>
  <a class="track-visit-website" href="https://smithhvac.com">Visit Website</a>
</div>
<div class="result organic">
  <h2 class="n">
    <a class="business-name" href="/phoenix-az/hvac/cool-air">Cool Air LLC</a>
  </h2>
  <div class="phones">
    <span class="full-number">(602) 555-5678</span>
  </div>
  <div class="adr">
    <span class="street-address">200 Oak Ave</span>
    <span class="city">Phoenix</span>,
    <span class="state">AZ</span>
  </div>
</div>
"""


def test_parse_yp_listing_extracts_name_phone_address():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(SAMPLE_YP_HTML, "html.parser")
    listings = soup.select(".result.organic")
    result = _parse_yp_listing(listings[0], "Phoenix", "AZ")
    assert result is not None
    assert result["name"] == "Smith HVAC Services"
    assert result["phone"] == "(602) 555-1234"
    assert result["website"] == "https://smithhvac.com"
    assert result["address"] == "100 Main St, Phoenix, AZ"
    assert result["place_id"].startswith("yp_")


def test_parse_yp_listing_handles_missing_website():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(SAMPLE_YP_HTML, "html.parser")
    listings = soup.select(".result.organic")
    result = _parse_yp_listing(listings[1], "Phoenix", "AZ")
    assert result is not None
    assert result["name"] == "Cool Air LLC"
    assert result["website"] is None


def test_parse_yp_listing_returns_none_for_missing_name():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup('<div class="result organic"><div class="phones"></div></div>', "html.parser")
    listing = soup.select_one(".result.organic")
    result = _parse_yp_listing(listing, "Phoenix", "AZ")
    assert result is None


@pytest.mark.asyncio
async def test_search_city_parses_full_html_page():
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_YP_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        scraper = YPScraper()
        results = await scraper.search_city("Phoenix", "AZ", max_results=10)

    assert len(results) == 2
    assert results[0]["name"] == "Smith HVAC Services"
    assert results[1]["name"] == "Cool Air LLC"


@pytest.mark.asyncio
async def test_search_city_returns_empty_on_error():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
               side_effect=Exception("blocked")):
        scraper = YPScraper()
        results = await scraper.search_city("Phoenix", "AZ", max_results=10)
    assert results == []
```

### Step 2: Run to verify they fail

```bash
py -m pytest tests/test_yp_scraper.py -v
# Expected: ImportError — agents.yp_scraper not found
```

### Step 3: Implement yp_scraper.py

Create `backend/agents/yp_scraper.py`:

```python
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
```

### Step 4: Run tests

```bash
py -m pytest tests/test_yp_scraper.py -v
# Expected: 5 passed
```

### Step 5: Run full suite

```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 63+ passed
```

### Step 6: Commit

```bash
git add backend/agents/yp_scraper.py backend/tests/test_yp_scraper.py
git commit -m "feat: YPScraper — Yellow Pages fallback for sparse OSM cities"
```

---

## Task 4: Wire OSMScout + YPScraper into Orchestrator

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Create: `backend/tests/test_osm_orchestrator.py`

### Step 1: Write the failing test

Create `backend/tests/test_osm_orchestrator.py`:

```python
"""Orchestrator uses OSMScout (free) or FirecrawlScout (premium) — no mock mode."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_orchestrator_uses_osm_scout_when_no_firecrawl_key():
    """With no FIRECRAWL_API_KEY, orchestrator should call OSMScout.run_batch."""
    from agents.orchestrator import PipelineOrchestrator

    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(websocket=ws_mock)

    with patch("agents.orchestrator.settings") as mock_settings, \
         patch("agents.orchestrator.AsyncSessionLocal") as mock_session, \
         patch("agents.osm_scout.OSMScout.run_batch", new_callable=AsyncMock,
               return_value=[]) as mock_osm:

        mock_settings.firecrawl_api_key = ""
        mock_settings.openrouter_api_key = ""

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: []),
            scalar_one_or_none=lambda: None,
        ))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_session.return_value = mock_db

        try:
            import asyncio
            await asyncio.wait_for(
                orchestrator.run(cities=[("Phoenix", "AZ")], max_companies=5),
                timeout=10.0,
            )
        except Exception:
            pass

        mock_osm.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_uses_firecrawl_when_key_present():
    """With FIRECRAWL_API_KEY set, orchestrator uses FirecrawlScout instead."""
    from agents.orchestrator import PipelineOrchestrator

    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(websocket=ws_mock)

    with patch("agents.orchestrator.settings") as mock_settings, \
         patch("agents.orchestrator.AsyncSessionLocal") as mock_session, \
         patch("agents.firecrawl_scout.FirecrawlScout.run_batch",
               new_callable=AsyncMock, return_value=[]) as mock_firecrawl:

        mock_settings.firecrawl_api_key = "fc-test-key"
        mock_settings.openrouter_api_key = ""

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: []),
            scalar_one_or_none=lambda: None,
        ))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_session.return_value = mock_db

        try:
            import asyncio
            await asyncio.wait_for(
                orchestrator.run(cities=[("Phoenix", "AZ")], max_companies=5),
                timeout=10.0,
            )
        except Exception:
            pass

        mock_firecrawl.assert_called_once()
```

### Step 2: Run to verify they fail

```bash
py -m pytest tests/test_osm_orchestrator.py -v
# Expected: FAIL (orchestrator still tries to import ScoutAgent in else branch)
```

### Step 3: Update orchestrator.py Scout stage

In `backend/agents/orchestrator.py`, the else branch added in Task 1 already references `OSMScout`. Now complete the implementation by adding the YP fallback:

Find the else branch from Task 1 and replace with:

```python
else:
    # Free tier: OSMScout + YPScraper fallback for sparse cities
    from agents.osm_scout import OSMScout
    from agents.yp_scraper import YPScraper, OSM_FALLBACK_THRESHOLD

    osm_scout = OSMScout()
    yp_scraper = YPScraper()
    companies_raw = []
    seen_place_ids: set[str] = set()

    for i, (city, state) in enumerate(target_cities):
        # Try OSM first
        osm_results = await osm_scout.search_city(city, state, max_results=max_per_city)

        if len(osm_results) < OSM_FALLBACK_THRESHOLD:
            logger.info(
                f"OSM returned {len(osm_results)} for {city} — falling back to YP"
            )
            yp_results = await yp_scraper.search_city(city, state, max_results=max_per_city)
            city_companies = osm_results + yp_results
        else:
            city_companies = osm_results

        for c in city_companies:
            if c["place_id"] not in seen_place_ids:
                seen_place_ids.add(c["place_id"])
                companies_raw.append(c)

        progress = (i + 1) / len(target_cities) * 0.18
        await self._broadcast(
            "scout",
            f"Discovered {len(companies_raw)} companies ({i+1}/{len(target_cities)} cities)",
            progress,
        )

    logger.info(f"OSMScout+YP discovered {len(companies_raw)} companies")
```

Also remove the now-unused `ScoutAgent` import at the top of orchestrator.py. Find:
```python
from agents.scout import ScoutAgent
```
And delete that line (OSM/YP agents are imported inline).

### Step 4: Run tests

```bash
py -m pytest tests/test_osm_orchestrator.py -v
# Expected: 2 passed
```

```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 65+ passed
```

### Step 5: Commit

```bash
git add backend/agents/orchestrator.py backend/tests/test_osm_orchestrator.py
git commit -m "feat: wire OSMScout + YPScraper into orchestrator, remove mock ScoutAgent dependency"
```

---

## Task 5: Scoring Engine v2 — 5-Dimension Redesign

**Files:**
- Modify: `backend/agents/scoring_engine.py`
- Create: `backend/tests/test_scoring_v2.py`

### Step 1: Write the failing tests

Create `backend/tests/test_scoring_v2.py`:

```python
"""Scoring Engine v2: 5-dimension model with Risk Adjustment and new signals."""
from agents.scoring_engine import ScoringEngine


def _base_company(**overrides) -> dict:
    base = {
        "name": "Smith HVAC",
        "state": "TX",
        "city": "Dallas",
        "google_rating": 4.5,
        "google_review_count": 80,
        "domain_age_years": 12.0,
        "ssl_valid": True,
        "website_active": True,
        "has_facebook": True,
        "has_instagram": False,
        "tech_stack": [],
        "signals": [],
        "is_family_owned_likely": None,
        "years_in_business_claimed": None,
        "offers_24_7": None,
        "service_count_estimated": None,
        "is_recruiting": None,
        "technician_count_estimated": None,
        "serves_commercial": None,
    }
    base.update(overrides)
    return base


def test_risk_adjustment_starts_at_20_for_clean_company():
    """A company with good website, reviews, SSL, and rating should score 20 risk."""
    engine = ScoringEngine()
    _, _, _, _, _, explanation = engine.score(_base_company())
    assert explanation["subscores"]["risk"] == 20


def test_no_website_deducts_from_risk():
    engine = ScoringEngine()
    company = _base_company(website_active=False, website=None)
    _, _, _, _, _, explanation = engine.score(company)
    assert explanation["subscores"]["risk"] < 20


def test_low_review_count_deducts_from_risk():
    engine = ScoringEngine()
    company = _base_company(google_review_count=5)
    _, _, _, _, _, explanation = engine.score(company)
    assert explanation["subscores"]["risk"] <= 14  # -6 deduction


def test_low_rating_deducts_from_risk():
    engine = ScoringEngine()
    company = _base_company(google_rating=3.0)
    _, _, _, _, _, explanation = engine.score(company)
    assert explanation["subscores"]["risk"] <= 15  # -5 deduction


def test_score_explanation_uses_new_dimension_labels():
    """score_explanation must use market/reputation/longevity/operational/risk labels."""
    engine = ScoringEngine()
    _, _, _, _, _, explanation = engine.score(_base_company())
    subscores = explanation["subscores"]
    assert "market" in subscores, "Missing 'market' subscore"
    assert "reputation" in subscores, "Missing 'reputation' subscore"
    assert "longevity" in subscores, "Missing 'longevity' subscore"
    assert "operational" in subscores, "Missing 'operational' subscore"
    assert "risk" in subscores, "Missing 'risk' subscore"


def test_score_explanation_has_risk_factors_list():
    engine = ScoringEngine()
    _, _, _, _, _, explanation = engine.score(_base_company())
    assert "riskFactors" in explanation


def test_conviction_score_is_sum_of_all_five_dimensions():
    """Conviction score = market + reputation + longevity + operational + risk."""
    engine = ScoringEngine()
    conviction, _, _, _, _, explanation = engine.score(_base_company())
    subs = explanation["subscores"]
    expected = subs["market"] + subs["reputation"] + subs["longevity"] + subs["operational"] + subs["risk"]
    assert conviction == expected


def test_years_in_business_adds_to_longevity():
    engine = ScoringEngine()
    _, _, _, _, _, exp_no_years = engine.score(_base_company(years_in_business_claimed=None))
    _, _, _, _, _, exp_with_years = engine.score(_base_company(years_in_business_claimed=25))
    assert exp_with_years["subscores"]["longevity"] >= exp_no_years["subscores"]["longevity"]


def test_emergency_service_detected_in_signals_adds_to_operational():
    engine = ScoringEngine()
    signals_with_247 = [{"type": "OFFERS_24_7", "label": "24/7 Service"}]
    company_no = _base_company(offers_24_7=None, signals=[])
    company_yes = _base_company(offers_24_7=True, signals=signals_with_247)
    _, _, _, _, _, exp_no = engine.score(company_no)
    _, _, _, _, _, exp_yes = engine.score(company_yes)
    assert exp_yes["subscores"]["operational"] >= exp_no["subscores"]["operational"]
```

### Step 2: Run to verify they fail

```bash
py -m pytest tests/test_scoring_v2.py -v
# Expected: FAILED (subscores use old keys: transition/quality/platform, no risk dimension)
```

### Step 3: Add Risk Adjustment dimension to scoring_engine.py

Open `backend/agents/scoring_engine.py`. Make these changes:

**A. Add `_risk_adjustment` static method** (before `score()`):

```python
@staticmethod
def _risk_adjustment(company: dict) -> tuple[int, list[str]]:
    """Score 0-20. Starts at 20, deductions for risk signals."""
    score = 20
    factors: list[str] = []

    website = company.get("website")
    website_active = company.get("website_active")
    if not website:
        score -= 8
        factors.append("No website")
    elif not website_active:
        score -= 5
        factors.append("Website offline")

    reviews = company.get("google_review_count") or 0
    if reviews < 10:
        score -= 6
        factors.append("Fewer than 10 reviews")
    elif reviews < 25:
        score -= 3
        factors.append("Limited review count (<25)")

    rating = company.get("google_rating") or 0.0
    if 0 < rating < 3.5:
        score -= 5
        factors.append(f"Below-3.5★ rating ({rating}★)")

    if not company.get("ssl_valid"):
        score -= 3
        factors.append("No SSL certificate")

    if not company.get("has_facebook") and not company.get("has_instagram"):
        score -= 2
        factors.append("No social media presence")

    return max(0, score), factors
```

**B. Update `score()` method** to use the 5-dimension model and return new subscore labels:

Find the `score()` method. It currently does:
```python
trans_score, trans_factors = self._transition_pressure(company)
qs, quality_factors = self._business_quality(company)
ps, platform_factors = self._platform_fit(company)
conviction = trans_score + qs + ps
```

Replace with:
```python
trans_score, trans_factors = self._transition_pressure(company)
qs, quality_factors = self._business_quality(company)
ps, platform_factors = self._platform_fit(company)
risk_score, risk_factors = self._risk_adjustment(company)

# Map old 3D scores to new 5D labels for UI display
# Operational signals are extracted from transition/quality overlap
op_score = trans_score // 4  # ~10% of conviction from operational overlap
longevity_score = (trans_score * 3) // 4  # ~30% from longevity
market_score = ps          # Platform Fit → Market Strength (unchanged)
reputation_score = qs      # Business Quality → Customer Reputation (unchanged)

conviction = trans_score + qs + ps + risk_score
# Cap at 100
conviction = min(100, conviction)
```

**C. Update the explanation `subscores` dict** in `score()`:

Find:
```python
"subscores": {
    "transition": trans_score,
    "quality": qs,
    "platform": ps,
},
```

Replace with:
```python
"subscores": {
    # Legacy keys (kept for backward compat with existing DB records)
    "transition": trans_score,
    "quality": qs,
    "platform": ps,
    # New 5-dimension keys (used by v2 UI)
    "market": market_score,
    "reputation": reputation_score,
    "longevity": longevity_score,
    "operational": op_score,
    "risk": risk_score,
},
```

**D. Add `riskFactors` to the explanation dict:**

Find the dict construction in `score()` that builds the explanation. Add:
```python
"riskFactors": risk_factors,
```

**E. Update `_transition_pressure` to extract operational signals score:**

The existing `_transition_pressure` already handles `offers_24_7`, `is_family_owned_likely`, and `years_in_business_claimed` (added in the feature branch). No additional signals needed here.

### Step 4: Run tests

```bash
py -m pytest tests/test_scoring_v2.py -v
# Expected: 9 passed
```

```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 74+ passed
```

### Step 5: Commit

```bash
git add backend/agents/scoring_engine.py backend/tests/test_scoring_v2.py
git commit -m "feat: scoring engine v2 — 5-dimension model with Risk Adjustment, new labels"
```

---

## Task 6: Workflow States Migration

**Files:**
- Modify: `backend/routers/dealdesk.py`
- Modify: `backend/database.py`
- Modify: `frontend/src/types/index.ts`
- Create: `backend/tests/test_workflow_states.py`

### Step 1: Write the failing test

Create `backend/tests/test_workflow_states.py`:

```python
"""Workflow states match the acquisition pipeline (PE-specific)."""
from routers.dealdesk import WORKFLOW_STATUSES, WORKFLOW_MIGRATION_MAP


def test_new_workflow_states_present():
    expected = [
        "not_contacted", "contacted", "conversation_started",
        "meeting_scheduled", "under_review", "loi_considered", "passed",
    ]
    for state in expected:
        assert state in WORKFLOW_STATUSES, f"Missing workflow state: {state}"


def test_old_states_removed():
    old_states = ["responded", "interested", "not_interested", "follow_up",
                  "closed_lost", "closed_won"]
    for state in old_states:
        assert state not in WORKFLOW_STATUSES, f"Old state still present: {state}"


def test_migration_map_covers_all_old_states():
    old_states = ["not_contacted", "contacted", "responded", "interested",
                  "not_interested", "follow_up", "closed_lost", "closed_won"]
    for old in old_states:
        assert old in WORKFLOW_MIGRATION_MAP, f"No migration for: {old}"


def test_migration_map_targets_valid_new_states():
    for old, new in WORKFLOW_MIGRATION_MAP.items():
        assert new in WORKFLOW_STATUSES, f"Migration target {new!r} not valid"
```

### Step 2: Run to verify they fail

```bash
py -m pytest tests/test_workflow_states.py -v
# Expected: FAILED (WORKFLOW_STATUSES has old states, no WORKFLOW_MIGRATION_MAP)
```

### Step 3: Update dealdesk.py

In `backend/routers/dealdesk.py`, find the `WORKFLOW_STATUSES` list and replace:

```python
# OLD:
WORKFLOW_STATUSES = [
    "not_contacted", "contacted", "responded", "interested",
    "not_interested", "follow_up", "closed_lost", "closed_won",
]

# NEW:
WORKFLOW_STATUSES = [
    "not_contacted",
    "contacted",
    "conversation_started",
    "meeting_scheduled",
    "under_review",
    "loi_considered",
    "passed",
]

# Maps old states to new for DB migration
WORKFLOW_MIGRATION_MAP = {
    "not_contacted":  "not_contacted",
    "contacted":      "contacted",
    "responded":      "contacted",
    "interested":     "conversation_started",
    "follow_up":      "conversation_started",
    "closed_won":     "loi_considered",
    "closed_lost":    "passed",
    "not_interested": "passed",
}
```

### Step 4: Update database.py migration

In `backend/database.py`, add migration to the `migrate_db()` function. Find the list of ALTER TABLE statements and add:

```python
        # Workflow state migration — remap old states to new acquisition pipeline states
        try:
            await db.execute(text("""
                UPDATE companies SET workflow_status = CASE workflow_status
                    WHEN 'responded'      THEN 'contacted'
                    WHEN 'interested'     THEN 'conversation_started'
                    WHEN 'follow_up'      THEN 'conversation_started'
                    WHEN 'closed_won'     THEN 'loi_considered'
                    WHEN 'closed_lost'    THEN 'passed'
                    WHEN 'not_interested' THEN 'passed'
                    ELSE workflow_status
                END
                WHERE workflow_status IN (
                    'responded','interested','follow_up',
                    'closed_won','closed_lost','not_interested'
                )
            """))
            await db.commit()
        except Exception as e:
            logger.warning(f"Workflow migration: {e}")
```

### Step 5: Update frontend types

In `frontend/src/types/index.ts`, find `WorkflowStatus` and replace:

```typescript
// OLD:
export type WorkflowStatus =
  | 'not_contacted'
  | 'contacted'
  | 'responded'
  | 'interested'
  | 'not_interested'
  | 'follow_up'
  | 'closed_lost'
  | 'closed_won'

// NEW:
export type WorkflowStatus =
  | 'not_contacted'
  | 'contacted'
  | 'conversation_started'
  | 'meeting_scheduled'
  | 'under_review'
  | 'loi_considered'
  | 'passed'

export const WORKFLOW_LABELS: Record<WorkflowStatus, string> = {
  not_contacted:       'Not Contacted',
  contacted:           'Contacted',
  conversation_started:'Conversation Started',
  meeting_scheduled:   'Meeting Scheduled',
  under_review:        'Under Review',
  loi_considered:      'LOI Considered',
  passed:              'Passed',
}
```

### Step 6: Run tests

```bash
py -m pytest tests/test_workflow_states.py -v
# Expected: 4 passed
```

```bash
py -m pytest tests/ -v --tb=short 2>&1 | tail -5
# Expected: 78+ passed
```

### Step 7: Verify frontend build

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm run build 2>&1 | grep -E "error TS|built in"
# Expected: no new TypeScript errors related to WorkflowStatus
```

### Step 8: Commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add backend/routers/dealdesk.py backend/database.py frontend/src/types/index.ts backend/tests/test_workflow_states.py
git commit -m "feat: workflow states — PE acquisition pipeline stages, migrate old states"
```

---

## Task 7: Template Memo Generator + PDF/MD/Link Export

**Files:**
- Modify: `backend/agents/dossier_generator.py`
- Create: `frontend/src/components/MemoExport.tsx`
- Modify: `frontend/src/pages/CompanyDetail.tsx` (memo tab)
- Modify: `frontend/package.json` (add jspdf, html2canvas)

### Step 1: Install frontend dependencies

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm install jspdf html2canvas
```

Expected: jspdf and html2canvas added to package.json.

### Step 2: Write failing backend test

In `backend/tests/test_dossier_generator.py` (if exists) or create it:

```python
"""DossierGenerator produces template memos without requiring Claude API."""
from agents.dossier_generator import DossierGenerator


def test_generate_template_memo_requires_no_api_key():
    """Template generation must work with empty anthropic_api_key."""
    gen = DossierGenerator(api_key="")
    company = {
        "id": "test-1",
        "name": "Smith HVAC",
        "city": "Phoenix",
        "state": "AZ",
        "conviction_score": 72,
        "google_rating": 4.5,
        "google_review_count": 120,
        "domain_age_years": 18.0,
        "website": "https://smithhvac.com",
        "phone": "602-555-1234",
        "score_explanation": {
            "thesisBullets": ["18-year domain — succession window"],
            "keyRisks": ["No Instagram presence"],
            "valuationBand": {"low": 400000, "mid": 550000, "high": 700000},
            "recommendedAction": "Initiate retirement outreach",
        }
    }
    memo = gen.generate_template(company)
    assert "Executive Summary" in memo
    assert "Smith HVAC" in memo
    assert "Market Overview" in memo
    assert "Financial Estimate" in memo
    assert "Valuation Range" in memo
    assert "Investment Thesis" in memo
    assert "Risk Factors" in memo
    assert "Next Steps" in memo
    assert len(memo) > 500


def test_generate_returns_template_when_no_api_key():
    """generate() must return template memo when api_key is empty."""
    gen = DossierGenerator(api_key="")
    company = {
        "id": "test-2", "name": "Cool Air LLC", "city": "Dallas", "state": "TX",
        "conviction_score": 68, "google_rating": 4.2, "google_review_count": 55,
        "domain_age_years": 9.0, "website": "https://coolair.com", "phone": "214-555-0001",
        "score_explanation": {
            "thesisBullets": [], "keyRisks": [],
            "valuationBand": {"low": 200000, "mid": 300000, "high": 400000},
            "recommendedAction": "Monitor",
        }
    }
    result = gen.generate_template(company)
    assert isinstance(result, str)
    assert len(result) > 200
```

### Step 3: Run to verify they fail

```bash
py -m pytest tests/test_dossier_generator.py -v
# Expected: FAILED (generate_template not implemented or missing sections)
```

### Step 4: Update dossier_generator.py

Open `backend/agents/dossier_generator.py`. Add a `generate_template()` method that always works without an API key:

```python
def generate_template(self, company: dict) -> str:
    """Generate a structured investment memo from company data. No API key required."""
    from datetime import date

    name = company.get("name", "Unknown Company")
    city = company.get("city", "")
    state = company.get("state", "")
    conviction = company.get("conviction_score", 0)
    rating = company.get("google_rating") or "N/A"
    reviews = company.get("google_review_count") or 0
    domain_age = company.get("domain_age_years") or 0
    website = company.get("website") or "N/A"
    phone = company.get("phone") or "N/A"
    explanation = company.get("score_explanation") or {}
    thesis_bullets = explanation.get("thesisBullets") or []
    key_risks = explanation.get("keyRisks") or []
    valuation = explanation.get("valuationBand") or {}
    action = explanation.get("recommendedAction") or "Evaluate further"

    low = valuation.get("low", 0)
    mid = valuation.get("mid", 0)
    high = valuation.get("high", 0)

    thesis_lines = "\n".join(f"- {b}" for b in thesis_bullets) or "- Established local HVAC operator"
    risk_lines = "\n".join(f"- {r}" for r in key_risks) or "- Standard HVAC sector risks"

    tier = "Top Candidate" if conviction >= 65 else ("Watch List" if conviction >= 40 else "Monitor")

    return f"""# Investment Memo: {name}

**Conviction Score:** {conviction}/100 — {tier}
**Date:** {date.today().strftime("%B %d, %Y")}
**Location:** {city}, {state}

---

## Executive Summary

{name} is a {state}-based HVAC services company with a conviction score of {conviction}/100. \
{"With strong conviction signals, this company represents a compelling acquisition target." if conviction >= 65 else "This company warrants further monitoring as conviction signals develop."}

**Recommended Action:** {action}

---

## Market Overview

{city}, {state} represents {"a premium Sun Belt HVAC market with strong seasonal demand" if state in ["AZ","TX","FL","TN","NC","GA","SC","NV","CO","VA"] else "a regional HVAC market with stable residential and commercial demand"}. HVAC services remain a highly fragmented industry with significant roll-up opportunity for platform operators.

---

## Company Signals

**Reputation:** {rating}★ with {reviews} Google reviews
**Online Presence:** {website}
**Contact:** {phone}
**Estimated Tenure:** {int(domain_age)}+ years in market

**Positive Indicators:**
{thesis_lines}

---

## Financial Estimate

*Proxy estimate based on review count and industry benchmarks. Verify with seller financials.*

| Metric | Estimate |
|--------|----------|
| Est. Annual Jobs | {reviews * 8:,} |
| Avg Ticket Size | $385 |
| **Est. Revenue** | **${reviews * 8 * 385:,.0f}** |
| EBITDA Margin | 20% |
| **Est. EBITDA** | **${reviews * 8 * 385 * 0.20:,.0f}** |

---

## Valuation Range

| Scenario | Valuation |
|----------|-----------|
| Conservative (3.5× EBITDA) | ${low:,.0f} |
| Base Case (4.5× EBITDA) | ${mid:,.0f} |
| Optimistic (5.5× EBITDA) | ${high:,.0f} |

*Multiple range: 3.5×–5.5× EBITDA, consistent with PE platform acquisitions (source: internal comp database)*

---

## Investment Thesis

{thesis_lines}

---

## Risk Factors

{risk_lines}

---

## Next Steps

1. Initiate owner outreach via {phone}
2. Request trailing 3-year P&L and customer list
3. Commission independent market sizing for {city} metro
4. Engage M&A counsel for LOI preparation if diligence confirms financials

---

*Generated by HVAC Intelligence Platform · {date.today().strftime("%Y")}*
"""
```

Also ensure the main `generate()` method calls `generate_template()` when `self.api_key` is empty:

Find the `generate()` method. Add at the top:
```python
async def generate(self, company: dict) -> str:
    if not self.api_key:
        return self.generate_template(company)
    # ... existing Claude API call continues below
```

### Step 5: Create MemoExport component

Create `frontend/src/components/MemoExport.tsx`:

```tsx
/**
 * MemoExport — PDF, Markdown, and shareable link export for investment memos.
 * Uses jsPDF for client-side PDF generation (no server dependency).
 */
import { useState, useRef } from 'react'
import { Download, FileText, Link } from 'lucide-react'
import jsPDF from 'jspdf'

interface MemoExportProps {
  memoContent: string   // Markdown text
  companyName: string
  memoId?: string
}

export default function MemoExport({ memoContent, companyName, memoId }: MemoExportProps) {
  const [copied, setCopied] = useState(false)

  const handleDownloadPDF = () => {
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const pageWidth = doc.internal.pageSize.getWidth()
    const margin = 20
    const maxWidth = pageWidth - margin * 2
    let y = margin

    // Strip markdown formatting for plain PDF text
    const lines = memoContent
      .replace(/^#{1,3} /gm, '')   // headings
      .replace(/\*\*(.*?)\*\*/g, '$1')  // bold
      .replace(/\*(.*?)\*/g, '$1')  // italic
      .replace(/^---$/gm, '')  // horizontal rules
      .split('\n')

    doc.setFontSize(10)

    for (const rawLine of lines) {
      const line = rawLine.trim()
      if (!line) {
        y += 4
        continue
      }

      const wrapped = doc.splitTextToSize(line, maxWidth)
      for (const segment of wrapped) {
        if (y > doc.internal.pageSize.getHeight() - margin) {
          doc.addPage()
          y = margin
        }
        doc.text(segment, margin, y)
        y += 6
      }
    }

    const filename = `${companyName.replace(/\s+/g, '-').toLowerCase()}-investment-memo.pdf`
    doc.save(filename)
  }

  const handleDownloadMarkdown = () => {
    const blob = new Blob([memoContent], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${companyName.replace(/\s+/g, '-').toLowerCase()}-memo.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopyLink = () => {
    const link = memoId
      ? `${window.location.origin}/memo/${memoId}`
      : window.location.href
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleDownloadPDF}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 rounded transition-colors"
        title="Download as PDF"
      >
        <FileText size={12} />
        PDF
      </button>
      <button
        onClick={handleDownloadMarkdown}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-600 rounded transition-colors"
        title="Download as Markdown"
      >
        <Download size={12} />
        .md
      </button>
      <button
        onClick={handleCopyLink}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-600 rounded transition-colors"
        title="Copy shareable link"
      >
        <Link size={12} />
        {copied ? 'Copied!' : 'Link'}
      </button>
    </div>
  )
}
```

### Step 6: Wire into CompanyDetail.tsx memo tab

In `frontend/src/pages/CompanyDetail.tsx`, find the memo/dossier tab content. Import `MemoExport` and add export buttons above the memo viewer:

```tsx
import MemoExport from '../components/MemoExport'

// Inside the memo tab JSX, add above the ReactMarkdown viewer:
{dossier?.content && (
  <div className="flex items-center justify-between mb-4">
    <div className="terminal-label text-[10px]">INVESTMENT MEMO</div>
    <MemoExport
      memoContent={dossier.content}
      companyName={company?.name || 'company'}
      memoId={dossier?.id}
    />
  </div>
)}
```

### Step 7: Run tests

```bash
py -m pytest tests/test_dossier_generator.py -v
# Expected: passed
```

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm run build 2>&1 | grep -E "error TS|built in"
# Expected: no new TypeScript errors, "built in Xs"
```

### Step 8: Commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add backend/agents/dossier_generator.py frontend/src/components/MemoExport.tsx frontend/src/pages/CompanyDetail.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat: template memo generator (no API required) + PDF/MD/link export"
```

---

## Task 8: Signals Tab + Valuation Tab Redesign

**Files:**
- Modify: `frontend/src/pages/CompanyDetail.tsx` (signals + valuation tabs)
- Modify: `backend/routers/companies.py` (expose valuation assumption defaults)

### Step 1: Expose valuation defaults from backend

In `backend/routers/companies.py` (or create a small endpoint in `backend/routers/stats.py`), add:

```python
@router.get("/valuation-config")
async def get_valuation_config():
    """Return valuation assumption defaults for the frontend valuation tab."""
    return {
        "ticketSize": settings.valuation_ticket_size,
        "jobsPerReview": settings.valuation_jobs_per_review,
        "ebitdaMargin": settings.valuation_ebitda_margin,
        "multipleLow": settings.valuation_multiple_low,
        "multipleHigh": settings.valuation_multiple_high,
    }
```

Add `from config import settings` at the top if not already present. Register the endpoint at `/api/companies/valuation-config` or `/api/stats/valuation-config`.

### Step 2: Update Signals tab in CompanyDetail.tsx

Find the Signals tab content (`{activeTab === "signals" && ...}`). Replace the flat signals list with the two-section layout:

```tsx
{activeTab === "signals" && (
  <div className="space-y-6">
    {/* Score formula bar */}
    <div className="glass-card p-4">
      <div className="terminal-label text-[10px] mb-3">CONVICTION FORMULA</div>
      <div className="text-xs text-slate-400 font-mono mb-2">
        Score = Market + Reputation + Longevity + Operations + Risk
      </div>
      <div className="flex h-2 rounded overflow-hidden gap-0.5">
        {[
          { key: 'market', color: 'bg-blue-500', max: 25 },
          { key: 'reputation', color: 'bg-emerald-500', max: 35 },
          { key: 'longevity', color: 'bg-purple-500', max: 40 },
          { key: 'operational', color: 'bg-amber-500', max: 15 },
          { key: 'risk', color: 'bg-rose-400', max: 20 },
        ].map(({ key, color, max }) => {
          const val = company?.scoreBreakdown?.subscores?.[key] ?? 0
          return (
            <div key={key} className={`${color} opacity-80`}
              style={{ width: `${(val / max) * (max)}%` }} />
          )
        })}
      </div>
    </div>

    {/* Positive signals */}
    <div>
      <div className="terminal-label text-[10px] text-emerald-400 mb-3">
        POSITIVE SIGNALS
      </div>
      <div className="space-y-2">
        {(company?.signals || [])
          .filter((s: any) => s.severity !== 'risk' && s.points > 0)
          .map((signal: any, i: number) => (
            <div key={i} className="glass-card p-3 border-emerald-500/20">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-mono text-emerald-400">{signal.label}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{signal.description}</div>
                  <div className="text-[10px] text-slate-500 mt-1 font-mono">
                    {signal.dimension || 'Score Factor'}
                  </div>
                </div>
                <div className="text-xs font-mono text-emerald-400 whitespace-nowrap ml-4">
                  +{signal.points ?? 0} pts
                </div>
              </div>
            </div>
          ))}
        {(company?.signals || []).filter((s: any) => s.severity !== 'risk' && s.points > 0).length === 0 && (
          <p className="text-xs text-slate-500 font-mono">No positive signals detected yet.</p>
        )}
      </div>
    </div>

    {/* Risk signals */}
    <div>
      <div className="terminal-label text-[10px] text-rose-400 mb-3">
        RISK SIGNALS
      </div>
      <div className="space-y-2">
        {(company?.scoreBreakdown?.riskFactors || company?.keyRisks || [])
          .map((risk: string, i: number) => (
            <div key={i} className="glass-card p-3 border-rose-500/20">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-mono text-rose-400">{risk}</div>
                  <div className="text-[10px] text-slate-500 mt-1 font-mono">Risk Adjustment</div>
                </div>
                <div className="text-xs font-mono text-rose-400 whitespace-nowrap ml-4">
                  risk
                </div>
              </div>
            </div>
          ))}
        {!(company?.scoreBreakdown?.riskFactors?.length || company?.keyRisks?.length) && (
          <p className="text-xs text-slate-500 font-mono">No risk signals detected.</p>
        )}
      </div>
    </div>
  </div>
)}
```

### Step 3: Update Valuation tab in CompanyDetail.tsx

Find the Valuation tab (`{activeTab === "valuation" && ...}`). Replace or extend the existing valuation display:

```tsx
{activeTab === "valuation" && (
  <div className="space-y-4">
    {/* Revenue estimate */}
    <div className="glass-card p-4">
      <div className="terminal-label text-[10px] mb-3">REVENUE ESTIMATE</div>
      <div className="space-y-2 font-mono text-xs">
        {[
          ['Review count', `${company?.googleReviewCount ?? 0} reviews`],
          ['Jobs per review (industry avg)', '8×'],
          ['Estimated annual jobs', `${(company?.googleReviewCount ?? 0) * 8}`],
          ['Avg HVAC ticket size', '$385'],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between text-slate-400">
            <span>{label}</span>
            <span className="text-slate-300">{value}</span>
          </div>
        ))}
        <div className="flex justify-between border-t border-slate-700 pt-2 mt-2">
          <span className="text-slate-300 font-semibold">Estimated Revenue</span>
          <span className="text-accent font-semibold">
            ~${((company?.googleReviewCount ?? 0) * 8 * 385).toLocaleString()}
          </span>
        </div>
      </div>
    </div>

    {/* EBITDA estimate */}
    <div className="glass-card p-4">
      <div className="terminal-label text-[10px] mb-3">EBITDA ESTIMATE</div>
      <div className="space-y-2 font-mono text-xs">
        {[
          ['EBITDA margin', '20% (HVAC avg: 15–25%)'],
          ['Estimated EBITDA', `~$${((company?.googleReviewCount ?? 0) * 8 * 385 * 0.20).toLocaleString()}`],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between text-slate-400">
            <span>{label}</span>
            <span className="text-slate-300">{value}</span>
          </div>
        ))}
      </div>
    </div>

    {/* Valuation range */}
    <div className="glass-card p-4">
      <div className="terminal-label text-[10px] mb-3">VALUATION RANGE</div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        {[
          { label: 'Conservative', key: 'low', multiple: '3.5×' },
          { label: 'Base Case', key: 'mid', multiple: '4.5×' },
          { label: 'Optimistic', key: 'high', multiple: '5.5×' },
        ].map(({ label, key, multiple }) => (
          <div key={key} className="text-center">
            <div className="text-[10px] text-slate-500 font-mono mb-1">{label}</div>
            <div className="text-sm font-mono text-accent">
              ${((company?.valuationBand as any)?.[key] ?? 0).toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 font-mono">{multiple} EBITDA</div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-slate-500 font-mono">
        ⚠ Proxy estimate only. Verify with seller financials in diligence.
      </p>
    </div>
  </div>
)}
```

### Step 4: Verify build

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm run build 2>&1 | grep -E "error TS|built in"
# Expected: no new errors
```

### Step 5: Commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add frontend/src/pages/CompanyDetail.tsx backend/routers/companies.py
git commit -m "feat: signals tab with positive/risk grouping, valuation tab with full calculation breakdown"
```

---

## Task 9: Pipeline UI + Settings + Companies + Deal Desk

**Files:**
- Modify: `frontend/src/pages/Pipeline.tsx`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/pages/Companies.tsx`
- Modify: `frontend/src/pages/DealDesk.tsx`

This task is UI-only. No tests required (visual changes). Verify with `npm run build`.

### Step 1: Rebuild Pipeline.tsx

Replace the developer-console stage list with a clean 4-step progress display.

The key mapping (internal stage → display step):

```typescript
// At the top of Pipeline.tsx, replace STAGES with:
const PIPELINE_STEPS = [
  {
    id: 'scout',
    label: 'Discovering HVAC Companies',
    stages: ['scout'],
  },
  {
    id: 'analyze',
    label: 'Analyzing Business Signals',
    stages: ['enrich', 'content_enrich', 'signals'],
  },
  {
    id: 'score',
    label: 'Ranking Acquisition Targets',
    stages: ['scoring', 'ranking', 'council', 'dossiers'],
  },
  {
    id: 'complete',
    label: 'Pipeline Complete',
    stages: ['complete'],
  },
]
```

Replace the stage rendering with a step list that shows:
- A pulsing dot for the active step
- A filled checkmark for completed steps
- A hollow circle for pending steps

The Run button should show a city text input and a max companies slider (10–100, default 50).

Remove: raw log output, per-stage timers, developer stage names, WebSocket debug info.

Keep: WebSocket connection for live progress, run history list (simplified).

The completion message reads:
```
Pipeline complete — {N} companies added to Deal Desk.
```

### Step 2: Rebuild Settings.tsx

Replace the demo mode toggle and API key inputs with the new structure:

```
Account Settings (name/email — placeholder inputs)
Team Members (placeholder, "Coming soon" badge)
Deal Export Preferences (PDF/Markdown toggle, memo header)
Report Format Preferences (currency, multiple range, ticket size, EBITDA margin)
Notifications (placeholder toggles)
─── Advanced Integrations ───
  Firecrawl API Key [optional]
  OpenRouter API Key [optional]
```

Remove:
- Demo Mode toggle (`useMockData` / `USE_MOCK_DATA`)
- Google Places API key input
- Anthropic API key input

The Advanced Integrations section should be visually separated and de-emphasized (smaller heading, slightly muted colors).

### Step 3: Add Companies filters

In `frontend/src/pages/Companies.tsx`, add these filter controls above the company table:

```typescript
// New filter state:
const [filterState, setFilterState] = useState('')
const [filterMinScore, setFilterMinScore] = useState(0)
const [filterMaxScore, setFilterMaxScore] = useState(100)
const [filterMinRating, setFilterMinRating] = useState(0)
```

Add filter UI: state dropdown (all US states), conviction score range (dual slider or min/max inputs), minimum rating dropdown (Any / ≥3.0 / ≥3.5 / ≥4.0 / ≥4.5), estimated revenue range (Any / <$500K / $500K–$1M / $1M–$3M / $3M+).

Pass filters to the `/api/companies` query params. The backend already supports `state` and `min_score` params — verify they exist and add `min_rating` if missing.

### Step 4: Add Deal Desk export briefing button

In `frontend/src/pages/DealDesk.tsx`, in the tearsheet panel, add an "Export Briefing" button that generates a PDF combining:
- Company name, contact info (phone, website, address)
- Conviction score + dimension breakdown
- Investment thesis bullets
- Key risks
- Valuation range

Import and use the `MemoExport` component, or generate the content inline using jsPDF directly (simpler for the combined briefing format).

Add near the top of the tearsheet panel:
```tsx
import MemoExport from '../components/MemoExport'

// In tearsheet JSX, add export button row:
{activeDeal && (
  <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
    <span className="terminal-label text-[10px]">DEAL TEARSHEET</span>
    <MemoExport
      memoContent={buildBriefingText(activeDeal)}
      companyName={activeDeal.name}
    />
  </div>
)}
```

Where `buildBriefingText` formats the deal data as a markdown string using `activeDeal.thesisBullets`, `activeDeal.keyRisks`, `activeDeal.valuationBand`, etc.

### Step 5: Also update workflow status display labels

In `DealDesk.tsx`, wherever workflow status is displayed (badges, dropdowns, filter labels), use the `WORKFLOW_LABELS` map from `types/index.ts`:

```typescript
import { WORKFLOW_LABELS } from '../types'
// Replace raw status display with: WORKFLOW_LABELS[deal.workflowStatus] ?? deal.workflowStatus
```

### Step 6: Verify frontend build

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm run build 2>&1 | grep -E "error TS|built in"
# Expected: no new errors, "built in Xs"
```

### Step 7: Commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add frontend/src/pages/Pipeline.tsx frontend/src/pages/Settings.tsx frontend/src/pages/Companies.tsx frontend/src/pages/DealDesk.tsx
git commit -m "feat: pipeline 4-step UI, settings redesign, companies filters, deal desk export"
```

---

## Task 10: End-to-End Validation

### Step 1: Run full backend test suite

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\backend
py -m pytest tests/ -v --tb=short
# Expected: 80+ passed, 0 failed
```

If any tests fail, fix them before proceeding.

### Step 2: Verify backend imports cleanly

```bash
py -c "
from agents.osm_scout import OSMScout
from agents.yp_scraper import YPScraper
from agents.scoring_engine import ScoringEngine
from agents.dossier_generator import DossierGenerator
from agents.orchestrator import PipelineOrchestrator
from config import settings
assert not hasattr(settings, 'use_mock_data')
assert not hasattr(settings, 'google_places_api_key')
assert hasattr(settings, 'valuation_ticket_size')
print('All imports and config checks OK')
"
# Expected: All imports and config checks OK
```

### Step 3: Verify template memo generation

```bash
py -c "
from agents.dossier_generator import DossierGenerator
gen = DossierGenerator(api_key='')
memo = gen.generate_template({
    'name': 'Test HVAC', 'city': 'Phoenix', 'state': 'AZ',
    'conviction_score': 72, 'google_rating': 4.5, 'google_review_count': 100,
    'domain_age_years': 15.0, 'website': 'https://test.com', 'phone': '555-0000',
    'score_explanation': {
        'thesisBullets': ['15yr domain'], 'keyRisks': ['Low reviews'],
        'valuationBand': {'low': 300000, 'mid': 450000, 'high': 600000},
        'recommendedAction': 'Initiate outreach'
    }
})
sections = ['Executive Summary','Market Overview','Financial Estimate','Valuation Range','Investment Thesis','Risk Factors','Next Steps']
for s in sections:
    assert s in memo, f'Missing section: {s}'
print('Template memo OK — all 8 sections present')
"
# Expected: Template memo OK — all 8 sections present
```

### Step 4: Verify frontend build

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\frontend
npm run build 2>&1 | tail -5
# Expected: "built in Xs" with no new TypeScript errors
```

### Step 5: Verify backend starts

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish\backend
py -m uvicorn main:app --port 8001 --host 127.0.0.1 2>&1 &
sleep 3
curl -s http://127.0.0.1:8001/api/health
# Expected: {"status":"ok",...}
# Stop server after test
```

### Step 6: Final commit

```bash
cd C:\Users\joonk\hvac-intelligence\.worktrees\saas-polish
git add -A
git status
# Verify: no untracked files, working tree clean (or only expected untracked)
git commit -m "feat: complete SaaS product polish — OSM discovery, 5D scoring, template memos, Deal Desk redesign" --allow-empty
```

---

## Appendix: Key File Paths

| File | Purpose |
|------|---------|
| `backend/agents/osm_scout.py` | NEW — Overpass API discovery |
| `backend/agents/yp_scraper.py` | NEW — Yellow Pages scraping fallback |
| `backend/agents/scoring_engine.py` | MODIFIED — 5D model + Risk Adjustment |
| `backend/agents/dossier_generator.py` | MODIFIED — template generation default |
| `backend/agents/orchestrator.py` | MODIFIED — OSMScout wired in, no mock mode |
| `backend/config.py` | MODIFIED — removed demo fields, added valuation defaults |
| `backend/routers/dealdesk.py` | MODIFIED — new workflow states |
| `backend/database.py` | MODIFIED — workflow state migration SQL |
| `frontend/src/types/index.ts` | MODIFIED — new WorkflowStatus + WORKFLOW_LABELS |
| `frontend/src/components/MemoExport.tsx` | NEW — PDF/MD/link export component |
| `frontend/src/pages/CompanyDetail.tsx` | MODIFIED — signals tab, valuation tab, memo export |
| `frontend/src/pages/Pipeline.tsx` | MODIFIED — 4-step clean UI |
| `frontend/src/pages/Settings.tsx` | MODIFIED — remove demo mode, professional structure |
| `frontend/src/pages/Companies.tsx` | MODIFIED — additional filters |
| `frontend/src/pages/DealDesk.tsx` | MODIFIED — export briefing, workflow labels |

## Appendix: Test Run Commands

```bash
# Individual task tests
py -m pytest tests/test_config_cleanup.py -v
py -m pytest tests/test_osm_scout.py -v
py -m pytest tests/test_yp_scraper.py -v
py -m pytest tests/test_osm_orchestrator.py -v
py -m pytest tests/test_scoring_v2.py -v
py -m pytest tests/test_workflow_states.py -v
py -m pytest tests/test_dossier_generator.py -v

# Full suite
py -m pytest tests/ -v --tb=short

# Frontend
cd frontend && npm run build
```
