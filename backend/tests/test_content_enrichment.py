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
