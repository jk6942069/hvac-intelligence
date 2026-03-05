"""Dashboard statistics API router."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Company, Dossier, PipelineRun
from auth import get_current_user, CurrentUser

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/dashboard")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    uid = user.user_id

    # Counts — all filtered to current user
    total = (await db.execute(
        select(func.count(Company.id)).where(Company.user_id == uid)
    )).scalar() or 0

    high_score = (await db.execute(
        select(func.count(Company.id)).where(
            and_(Company.user_id == uid, Company.score >= 65)
        )
    )).scalar() or 0

    top_candidates = (await db.execute(
        select(func.count(Company.id)).where(
            and_(
                Company.user_id == uid,
                Company.status.in_(["top_candidate", "dossier_generated"]),
            )
        )
    )).scalar() or 0

    # Dossier count: Dossier has no user_id — join via company
    user_company_ids = select(Company.id).where(Company.user_id == uid).scalar_subquery()
    dossiers = (await db.execute(
        select(func.count(Dossier.id)).where(Dossier.company_id.in_(user_company_ids))
    )).scalar() or 0

    avg_score_res = (await db.execute(
        select(func.avg(Company.score)).where(Company.user_id == uid)
    )).scalar()
    avg_score = round(float(avg_score_res or 0), 1)

    pipeline_runs = (await db.execute(
        select(func.count(PipelineRun.id)).where(PipelineRun.user_id == uid)
    )).scalar() or 0

    # Score distribution — user's companies only
    score_ranges = [(0, 30, "0–30"), (30, 50, "30–50"), (50, 65, "50–65"),
                    (65, 80, "65–80"), (80, 101, "80–100")]
    distribution = []
    for lo, hi, label in score_ranges:
        cnt = (await db.execute(
            select(func.count(Company.id)).where(
                and_(Company.user_id == uid, Company.score >= lo, Company.score < hi)
            )
        )).scalar() or 0
        distribution.append({"range": label, "count": cnt})

    # Top states — user's companies only
    state_res = await db.execute(
        select(Company.state, func.count(Company.id).label("cnt"))
        .where(Company.user_id == uid)
        .group_by(Company.state)
        .order_by(func.count(Company.id).desc())
        .limit(8)
    )
    top_states = [{"state": r[0] or "—", "count": r[1]} for r in state_res]

    # Recent top targets — user's companies only
    targets_res = await db.execute(
        select(Company)
        .where(
            and_(
                Company.user_id == uid,
                Company.status.in_(["top_candidate", "dossier_generated"]),
            )
        )
        .order_by(Company.score.desc())
        .limit(6)
    )
    targets = targets_res.scalars().all()

    return {
        "totalCompanies": total,
        "highScoreCompanies": high_score,
        "topCandidates": top_candidates,
        "dossiersGenerated": dossiers,
        "avgScore": avg_score,
        "pipelineRuns": pipeline_runs,
        "scoreDistribution": distribution,
        "topStates": top_states,
        "recentTargets": [
            {
                "id": c.id,
                "name": c.name,
                "city": c.city,
                "state": c.state,
                "score": c.score,
                "rank": c.rank,
                "googleRating": c.google_rating,
                "googleReviewCount": c.google_review_count,
                "signals": c.signals or [],
                "status": c.status,
            }
            for c in targets
        ],
    }
