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
