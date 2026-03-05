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
    with_recruiting = engine.score(make_company(is_recruiting=True))
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
