"""Verify protected routes reject unauthenticated requests."""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def app():
    from main import app
    # Initialize DB for tests
    from database import init_db, migrate_db
    await init_db()
    await migrate_db()
    return app


@pytest.mark.anyio
async def test_companies_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/companies")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_dealdesk_feed_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/dealdesk/feed")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_pipeline_run_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/pipeline/run", json={})
    assert r.status_code == 401


@pytest.mark.anyio
async def test_pipeline_status_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/pipeline/status")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_health_is_public(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_stats_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/stats/dashboard")
    assert r.status_code == 401
