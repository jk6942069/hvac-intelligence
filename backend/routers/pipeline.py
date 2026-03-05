"""Pipeline control API router + WebSocket."""
import asyncio
import logging
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from pydantic import BaseModel
from database import AsyncSessionLocal
from models import PipelineRun
from auth import get_current_user, CurrentUser, get_current_user_ws

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Global state
_orchestrator = None
_ws_connections: list[WebSocket] = []


async def _broadcast_ws(message: dict):
    dead = []
    for ws in _ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            _ws_connections.remove(ws)
        except ValueError:
            pass


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from agents.orchestrator import PipelineOrchestrator
        _orchestrator = PipelineOrchestrator(ws_broadcast=_broadcast_ws)
    return _orchestrator


class RunConfig(BaseModel):
    cities: Optional[List[str]] = None   # "City, ST" strings
    states: Optional[List[str]] = None   # state abbreviations
    max_companies: int = 200
    generate_dossiers_for_top: int = 20


@router.post("/run")
async def start_pipeline(
    config: RunConfig,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    import uuid
    from agents.scout import DEFAULT_CITIES

    orch = _get_orchestrator()
    if orch.is_running:
        return {"status": "already_running", "run_id": orch.current_run_id}

    # Resolve target cities
    target_cities = DEFAULT_CITIES
    if config.cities:
        parsed = []
        for s in config.cities:
            parts = s.split(",")
            if len(parts) == 2:
                parsed.append((parts[0].strip(), parts[1].strip()))
        if parsed:
            target_cities = parsed
    elif config.states:
        upper_states = [s.upper() for s in config.states]
        filtered = [(c, s) for c, s in DEFAULT_CITIES if s in upper_states]
        if filtered:
            target_cities = filtered

    run_id = str(uuid.uuid4())

    async def _run():
        await orch.run(
            cities=target_cities,
            max_companies=config.max_companies,
            generate_dossiers_for_top=config.generate_dossiers_for_top,
            run_id=run_id,
        )

    background_tasks.add_task(_run)
    return {"status": "started", "run_id": run_id}


@router.get("/status")
async def pipeline_status(user: CurrentUser = Depends(get_current_user)):
    orch = _get_orchestrator()
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PipelineRun)
            .where(PipelineRun.user_id == user.user_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(1)
        )
        last = res.scalar_one_or_none()

    def _fmt(r: PipelineRun):
        return {
            "id": r.id,
            "status": r.status,
            "stage": r.current_stage,
            "total": r.total_companies,
            "processed": r.processed_companies,
            "startedAt": r.started_at.isoformat() if r.started_at else None,
            "completedAt": r.completed_at.isoformat() if r.completed_at else None,
            "error": r.error,
        }

    return {
        "isRunning": orch.is_running,
        "currentRunId": orch.current_run_id,
        "lastRun": _fmt(last) if last else None,
    }


@router.get("/history")
async def pipeline_history(user: CurrentUser = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(PipelineRun)
            .where(PipelineRun.user_id == user.user_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(25)
        )
        runs = res.scalars().all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "stage": r.current_stage,
            "total": r.total_companies,
            "processed": r.processed_companies,
            "startedAt": r.started_at.isoformat() if r.started_at else None,
            "completedAt": r.completed_at.isoformat() if r.completed_at else None,
            "error": r.error,
        }
        for r in runs
    ]


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = ""):
    await websocket.accept()
    if token:
        try:
            async with AsyncSessionLocal() as db:
                await get_current_user_ws(token, db)
        except Exception:
            await websocket.close(code=4001)
            return
    _ws_connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(25)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            _ws_connections.remove(websocket)
        except ValueError:
            pass
