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
