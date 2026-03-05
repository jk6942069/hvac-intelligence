"""Test scan quota enforcement."""
import pytest
from fastapi import HTTPException
from auth import CurrentUser


def make_user(plan: str, scans_used: int) -> CurrentUser:
    return CurrentUser(user_id="uid-1", email="x@y.com", plan=plan, scans_used_this_month=scans_used)


def test_starter_within_limit_passes():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("starter", 5))  # should not raise


def test_starter_at_limit_raises_429():
    from routers.pipeline import check_scan_quota
    with pytest.raises(HTTPException) as exc:
        check_scan_quota(make_user("starter", 10))
    assert exc.value.status_code == 429


def test_professional_unlimited():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("professional", 9999))  # should not raise


def test_enterprise_unlimited():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("enterprise", 9999))  # should not raise
