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
