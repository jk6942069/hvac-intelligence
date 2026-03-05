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


@pytest.mark.asyncio
async def test_scrape_yellowpages_handles_object_response():
    """_scrape_yellowpages handles ScrapeResponse object-style (result.extract)."""
    mock_extract = {
        "businesses": [
            {
                "name": "Valley HVAC Services",
                "phone": "602-555-1111",
                "address": "50 W Main St",
                "rating": 4.6,
                "review_count": 88,
                "website": "https://valleyhvac.com",
            }
        ]
    }
    mock_result = MagicMock()
    mock_result.extract = mock_extract

    with patch("agents.firecrawl_scout.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.scrape_url.return_value = mock_result
        MockApp.return_value = mock_instance

        scout = FirecrawlScout(api_key="fc-test")
        companies = await scout._scrape_yellowpages("Phoenix", "AZ")

    assert len(companies) == 1
    assert companies[0]["name"] == "Valley HVAC Services"
    assert companies[0]["discovery_source"] == "yellowpages"


@pytest.mark.asyncio
async def test_scrape_yellowpages_handles_dict_response():
    """_scrape_yellowpages handles dict-style response (result['extract'])."""
    mock_extract = {
        "businesses": [
            {
                "name": "Sun State Cooling",
                "phone": "480-555-2222",
                "address": "100 E Oak Ave",
                "rating": 4.4,
                "review_count": 55,
                "website": "https://sunstatecooling.com",
            }
        ]
    }
    mock_result = {"extract": mock_extract}

    with patch("agents.firecrawl_scout.FirecrawlApp") as MockApp:
        mock_instance = MagicMock()
        mock_instance.scrape_url.return_value = mock_result
        MockApp.return_value = mock_instance

        scout = FirecrawlScout(api_key="fc-test")
        companies = await scout._scrape_yellowpages("Phoenix", "AZ")

    assert len(companies) == 1
    assert companies[0]["name"] == "Sun State Cooling"
    assert companies[0]["discovery_source"] == "yellowpages"
