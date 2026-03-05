"""Orchestrator uses OSMScout (free) or FirecrawlScout (premium) — no mock mode."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_orchestrator_uses_osm_scout_when_no_firecrawl_key():
    """With no FIRECRAWL_API_KEY, orchestrator should call OSMScout.run_batch."""
    from agents.orchestrator import PipelineOrchestrator

    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(ws_broadcast=ws_mock)

    with patch("agents.orchestrator.settings") as mock_settings, \
         patch("agents.orchestrator.AsyncSessionLocal") as mock_session, \
         patch("agents.osm_scout.OSMScout.run_batch", new_callable=AsyncMock,
               return_value=[]) as mock_osm:

        mock_settings.firecrawl_api_key = ""
        mock_settings.openrouter_api_key = ""

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: []),
            scalar_one_or_none=lambda: None,
        ))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_session.return_value = mock_db

        try:
            import asyncio
            await asyncio.wait_for(
                orchestrator.run(cities=[("Phoenix", "AZ")], max_companies=5),
                timeout=10.0,
            )
        except Exception:
            pass

        mock_osm.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_uses_firecrawl_when_key_present():
    """With FIRECRAWL_API_KEY set, orchestrator uses FirecrawlScout instead."""
    from agents.orchestrator import PipelineOrchestrator

    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(ws_broadcast=ws_mock)

    with patch("agents.orchestrator.settings") as mock_settings, \
         patch("agents.orchestrator.AsyncSessionLocal") as mock_session, \
         patch("agents.firecrawl_scout.FirecrawlScout.run_batch",
               new_callable=AsyncMock, return_value=[]) as mock_firecrawl:

        mock_settings.firecrawl_api_key = "fc-test-key"
        mock_settings.openrouter_api_key = ""

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalars=lambda: MagicMock(all=lambda: []),
            scalar_one_or_none=lambda: None,
        ))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_session.return_value = mock_db

        try:
            import asyncio
            await asyncio.wait_for(
                orchestrator.run(cities=[("Phoenix", "AZ")], max_companies=5),
                timeout=10.0,
            )
        except Exception:
            pass

        mock_firecrawl.assert_called_once()
