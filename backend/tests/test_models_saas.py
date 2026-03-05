"""Verify new SaaS models have correct fields."""
from models import User, Company, PipelineRun, Memo


def test_user_model_has_plan_field():
    u = User(id="test-uid", email="test@example.com")
    assert u.plan == "starter"
    assert u.scans_used_this_month == 0


def test_company_has_user_id():
    assert hasattr(Company, "user_id")


def test_pipeline_run_has_user_id_and_cities():
    assert hasattr(PipelineRun, "user_id")
    assert hasattr(PipelineRun, "cities")


def test_memo_has_user_id():
    assert hasattr(Memo, "user_id")


def test_google_place_id_not_unique():
    """Two users can have the same company — google_place_id must not be globally unique."""
    col = Company.__table__.c.google_place_id
    # unique constraint should not exist on this column
    assert not col.unique, "google_place_id should not be unique (multi-tenant: two users can have same company)"
