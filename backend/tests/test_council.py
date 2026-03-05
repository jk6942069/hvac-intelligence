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
