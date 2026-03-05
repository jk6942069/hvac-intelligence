"""
Agent 7 — Pipeline Orchestrator
Coordinates all agents, manages state, streams progress via WebSocket.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Callable
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.scout import ScoutAgent, DEFAULT_CITIES
from agents.enrichment import EnrichmentAgent
from agents.signal_analyst import SignalAnalyst
from agents.scoring_engine import ScoringEngine
from agents.ranking_engine import RankingEngine
from agents.dossier_generator import DossierGenerator
from models import Company, PipelineRun, Dossier
from database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self, ws_broadcast: Optional[Callable] = None):
        self.ws_broadcast = ws_broadcast
        self.current_run_id: Optional[str] = None
        self.is_running = False

    async def _broadcast(self, stage: str, message: str, progress: float = 0.0, extra: dict = None):
        if self.ws_broadcast:
            try:
                await self.ws_broadcast({
                    "type": "progress",
                    "stage": stage,
                    "message": message,
                    "progress": round(min(progress, 1.0), 3),
                    **(extra or {}),
                })
            except Exception as e:
                logger.debug(f"WS broadcast failed: {e}")

    async def _save_run(self, run_id: str, **values):
        async with AsyncSessionLocal() as db:
            await db.execute(update(PipelineRun).where(PipelineRun.id == run_id).values(**values))
            await db.commit()

    async def run(
        self,
        cities: list[tuple[str, str]] = None,
        max_companies: int = 200,
        generate_dossiers_for_top: int = 20,
        run_id: str = None,
    ) -> str:
        if self.is_running:
            raise ValueError("A pipeline run is already in progress.")

        self.is_running = True
        run_id = run_id or str(uuid.uuid4())
        self.current_run_id = run_id

        async with AsyncSessionLocal() as db:
            pr = PipelineRun(
                id=run_id,
                status="running",
                config_json={"max_companies": max_companies},
            )
            db.add(pr)
            await db.commit()

        try:
            # ─── STAGE 1: Scout ─────────────────────────────────────────
            await self._broadcast("scout", "Discovering HVAC companies…", 0.0)
            all_cities = cities or DEFAULT_CITIES
            # Trim city list so max_per_city is always at least 8
            max_per_city = max(8, max_companies // max(len(all_cities), 1))
            num_cities = min(len(all_cities), max(1, max_companies // max_per_city + 1))
            target_cities = all_cities[:num_cities]

            scout = ScoutAgent()
            companies_raw = await scout.run_batch(
                target_cities,
                max_per_city=max_per_city,
                progress_callback=lambda m, p: self._broadcast("scout", m, p * 0.18),
            )
            companies_raw = companies_raw[:max_companies]
            total = len(companies_raw)
            logger.info(f"Scout complete: {total} companies")
            await self._broadcast("scout", f"Found {total} HVAC companies", 0.20)
            await self._save_run(run_id, current_stage="scout_complete", total_companies=total)

            # ─── Persist initial records ─────────────────────────────────
            async with AsyncSessionLocal() as db:
                for c in companies_raw:
                    res = await db.execute(
                        select(Company).where(Company.google_place_id == c.get("place_id"))
                    )
                    existing = res.scalar_one_or_none()
                    if existing:
                        c["id"] = existing.id
                        existing.name = c.get("name", existing.name)
                        existing.google_rating = c.get("google_rating")
                        existing.google_review_count = c.get("google_review_count")
                        existing.status = "scouted"
                    else:
                        cid = str(uuid.uuid4())
                        c["id"] = cid
                        db.add(Company(
                            id=cid,
                            name=c.get("name", ""),
                            address=c.get("address", ""),
                            city=c.get("city", ""),
                            state=c.get("state", ""),
                            phone=c.get("phone", ""),
                            website=c.get("website", ""),
                            google_place_id=c.get("place_id"),
                            google_rating=c.get("google_rating"),
                            google_review_count=c.get("google_review_count"),
                            category="HVAC",
                            status="scouted",
                            raw_google_data=c.get("raw_google_data"),
                        ))
                await db.commit()

            # ─── STAGE 2: Enrich ─────────────────────────────────────────
            await self._broadcast("enrich", "Enriching company data…", 0.20)
            enricher = EnrichmentAgent()
            try:
                companies_enriched = await enricher.enrich_batch(
                    companies_raw,
                    progress_callback=lambda m, p: self._broadcast("enrich", m, 0.20 + p * 0.20),
                )
            finally:
                await enricher.close()

            async with AsyncSessionLocal() as db:
                for c in companies_enriched:
                    await db.execute(
                        update(Company).where(Company.id == c.get("id")).values(
                            domain=c.get("domain"),
                            domain_age_years=c.get("domain_age_years"),
                            ssl_valid=c.get("ssl_valid"),
                            ssl_expiry=c.get("ssl_expiry"),
                            tech_stack=c.get("tech_stack", []),
                            website_active=c.get("website_active"),
                            website_load_time_ms=c.get("website_load_time_ms"),
                            website_last_checked=c.get("website_last_checked"),
                            has_facebook=c.get("has_facebook", False),
                            has_instagram=c.get("has_instagram", False),
                            website_outdated=c.get("website_outdated", False),
                            status="enriched",
                        )
                    )
                await db.commit()

            await self._broadcast("enrich", f"Enriched {len(companies_enriched)} companies", 0.40)

            # ─── STAGE 3: Signal Analysis ────────────────────────────────
            await self._broadcast("signals", "Analyzing transition signals…", 0.40)
            analyst = SignalAnalyst()
            companies_signals = analyst.analyze_batch(companies_enriched)
            await self._broadcast("signals", "Signal analysis complete", 0.55)

            # ─── STAGE 4: Scoring ────────────────────────────────────────
            await self._broadcast("scoring", "Scoring acquisition probability…", 0.55)
            scorer = ScoringEngine()
            companies_scored = scorer.score_batch(companies_signals)
            await self._broadcast("scoring", "Scoring complete", 0.65)

            # ─── STAGE 5: Ranking ────────────────────────────────────────
            await self._broadcast("ranking", "Ranking candidates…", 0.65)
            ranker = RankingEngine()
            companies_ranked = ranker.rank(companies_scored)

            async with AsyncSessionLocal() as db:
                for c in companies_ranked:
                    await db.execute(
                        update(Company).where(Company.id == c.get("id")).values(
                            signals=c.get("signals", []),
                            score=c.get("score", 0),
                            conviction_score=c.get("conviction_score", 0),
                            score_breakdown=c.get("score_breakdown", {}),
                            transition_score=c.get("transition_score", 0),
                            quality_score=c.get("quality_score", 0),
                            platform_score=c.get("platform_score", 0),
                            score_explanation=c.get("score_explanation"),
                            rank=c.get("rank"),
                            status=c.get("status", "ranked"),
                        )
                    )
                await db.commit()

            await self._broadcast("ranking", f"Ranked {len(companies_ranked)} companies", 0.75)

            # ─── STAGE 6: Dossiers ───────────────────────────────────────
            top = [c for c in companies_ranked if c.get("status") == "top_candidate"]
            top = top[:generate_dossiers_for_top]
            await self._broadcast("dossiers", f"Writing dossiers for {len(top)} top targets…", 0.75)

            dossier_gen = DossierGenerator()
            dossier_results = await dossier_gen.generate_batch(
                top,
                progress_callback=lambda m, p: self._broadcast("dossiers", m, 0.75 + p * 0.22),
            )

            async with AsyncSessionLocal() as db:
                for company_id, content in dossier_results:
                    res = await db.execute(select(Dossier).where(Dossier.company_id == company_id))
                    existing_d = res.scalar_one_or_none()
                    if existing_d:
                        existing_d.content = content
                        existing_d.generated_at = datetime.utcnow()
                    else:
                        db.add(Dossier(
                            id=str(uuid.uuid4()),
                            company_id=company_id,
                            content=content,
                        ))
                    await db.execute(
                        update(Company).where(Company.id == company_id)
                        .values(status="dossier_generated")
                    )
                await db.commit()

            # ─── Finalize ────────────────────────────────────────────────
            await self._save_run(
                run_id,
                status="completed",
                current_stage="complete",
                total_companies=total,
                processed_companies=total,
                completed_at=datetime.utcnow(),
            )
            await self._broadcast(
                "complete",
                f"Pipeline complete — {len(top)} dossiers ready.",
                1.0,
                {"run_id": run_id},
            )
            if self.ws_broadcast:
                await self.ws_broadcast({"type": "complete", "run_id": run_id})

        except Exception as e:
            logger.exception(f"Pipeline run {run_id} failed: {e}")
            await self._save_run(
                run_id,
                status="failed",
                error=str(e),
                completed_at=datetime.utcnow(),
            )
            if self.ws_broadcast:
                await self.ws_broadcast({"type": "error", "message": str(e)})
        finally:
            self.is_running = False
            self.current_run_id = None

        return run_id
