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


def test_custom_min_signals_override():
    # A thin company (only 1 non-null signal) normally fails
    thin = make_company(
        is_family_owned_likely=None,
        offers_24_7=None,
        service_count_estimated=None,
        years_in_business_claimed=None,
        is_recruiting=True,   # Only this one
        technician_count_estimated=None,
        serves_commercial=None,
    )
    # With min_signals=1 it should pass (override allows thin company through)
    assert qualifies_for_council(thin, min_signals=1) is True
    # With min_signals=7 a company with only 5 signals fails
    company_5_signals = make_company(is_recruiting=None, technician_count_estimated=None)
    assert qualifies_for_council(company_5_signals, min_signals=7) is False
