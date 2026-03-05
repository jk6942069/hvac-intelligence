"""
HVAC Intelligence Engine -- FastAPI Application
Deal origination intelligence for HVAC acquisition targets.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from database import init_db, migrate_db, AsyncSessionLocal
from routers.companies import router as companies_router
from routers.pipeline import router as pipeline_router
from routers.dossiers import router as dossiers_router
from routers.stats import router as stats_router
from routers.dealdesk import router as dealdesk_router
from routers.workflow import router as workflow_router
from routers.comps import router as comps_router, seed_comps
from routers.memos import router as memos_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HVAC Intelligence Engine starting up...")
    await init_db()
    await migrate_db()
    logger.info("Database ready (schema migrated).")
    # Seed reference data
    async with AsyncSessionLocal() as db:
        await seed_comps(db)
    logger.info("Comp deals seeded.")
    # Re-score all companies on startup if they have no conviction score
    try:
        await _rescore_unscored_companies()
    except Exception as e:
        logger.warning(f"Startup re-scoring skipped: {e}")
    yield
    logger.info("Shutting down.")


async def _rescore_unscored_companies():
    """Re-run scoring on companies that predate the v2 scoring engine."""
    from sqlalchemy import select, or_
    from models import Company
    from agents.scoring_engine import ScoringEngine

    engine = ScoringEngine()
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Company).where(
                or_(Company.conviction_score == None, Company.conviction_score == 0)
            ).limit(500)
        )
        companies = res.scalars().all()
        if not companies:
            return

        logger.info(f"Re-scoring {len(companies)} companies with v2 engine...")
        for c in companies:
            if not c.signals:
                continue  # skip unenriched
            company_dict = {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "state": c.state,
                "domain_age_years": c.domain_age_years,
                "ssl_valid": c.ssl_valid,
                "ssl_expiry": c.ssl_expiry,
                "website_active": c.website_active,
                "tech_stack": c.tech_stack,
                "website_load_time_ms": c.website_load_time_ms,
                "google_review_count": c.google_review_count,
                "google_rating": c.google_rating,
                "has_facebook": c.has_facebook,
                "has_instagram": c.has_instagram,
                "signals": c.signals,
                "workflow_status": c.workflow_status,
            }
            conviction, breakdown, ts, qs, ps, explanation = engine.score(company_dict)
            c.score = conviction
            c.conviction_score = conviction
            c.score_breakdown = breakdown
            c.transition_score = ts
            c.quality_score = qs
            c.platform_score = ps
            c.score_explanation = explanation

        await db.commit()
        logger.info(f"Re-scored {len(companies)} companies.")


app = FastAPI(
    title="HVAC Intelligence Engine",
    description="Deal origination intelligence for HVAC acquisition targets",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(companies_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(dossiers_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(dealdesk_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(comps_router, prefix="/api")
app.include_router(memos_router, prefix="/api")


@app.get("/api/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "hasAnthropicKey": bool(settings.anthropic_api_key),
        "hasFirecrawlKey": bool(settings.firecrawl_api_key),
    }


class ConfigUpdate(BaseModel):
    anthropicApiKey: Optional[str] = None
    batchSize: Optional[int] = None


@app.get("/api/config", tags=["system"])
async def get_config():
    return {
        "anthropicApiKey": "••••••••" if settings.anthropic_api_key else "",
        "batchSize": settings.batch_size,
        "hasAnthropicKey": bool(settings.anthropic_api_key),
        "hasFirecrawlKey": bool(settings.firecrawl_api_key),
    }


@app.put("/api/config", tags=["system"])
async def update_config(body: ConfigUpdate):
    if body.anthropicApiKey is not None:
        settings.anthropic_api_key = body.anthropicApiKey
    if body.batchSize is not None:
        settings.batch_size = body.batchSize
    return {"status": "updated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
