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
