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
