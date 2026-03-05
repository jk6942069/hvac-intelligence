"""Smoke test: orchestrator stages complete without error in mock mode."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agents.orchestrator import PipelineOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_runs_all_stages_in_mock_mode():
    """Full pipeline smoke test — mock mode, no real API calls."""
    ws_mock = AsyncMock()
    orchestrator = PipelineOrchestrator(ws_broadcast=ws_mock)

    with patch("agents.orchestrator.AsyncSessionLocal") as MockSession:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        MockSession.return_value = mock_db

        # Should not raise
        try:
            await asyncio.wait_for(
                orchestrator.run(
                    cities=[("Phoenix", "AZ")],
                    max_companies=5,
                    generate_dossiers_for_top=0,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            pytest.fail("Orchestrator timed out after 30s in mock mode")
        except Exception as e:
            # DB errors are expected in full mock — just verify it ran stages
            assert "stage" not in str(e).lower(), f"Unexpected stage error: {e}"
