"""Test billing endpoint structure."""


def test_plan_display_defined():
    from routers.billing import PLAN_DISPLAY
    assert "starter" in PLAN_DISPLAY
    assert "professional" in PLAN_DISPLAY
    assert "enterprise" in PLAN_DISPLAY


def test_billing_router_has_correct_routes():
    from routers.billing import router
    paths = [r.path for r in router.routes]
    assert "/create-checkout" in paths
    assert "/webhook" in paths
    assert "/portal" in paths
    assert "/status" in paths
