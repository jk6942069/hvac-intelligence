"""Deal Desk API -- primary investor-facing ranked feed."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Company, Dossier, Memo

router = APIRouter(prefix="/dealdesk", tags=["dealdesk"])

WORKFLOW_STATUSES = [
    "not_contacted", "contacted", "responded", "interested",
    "not_interested", "follow_up", "closed_lost", "closed_won",
]


def company_to_deal(c: Company, has_dossier: bool = False, has_memo: bool = False) -> dict:
    """Serialize a company into a Deal Desk card payload."""
    explanation = c.score_explanation or {}
    return {
        "id": c.id,
        "name": c.name,
        "city": c.city,
        "state": c.state,
        "phone": c.phone,
        "website": c.website,
        "address": c.address,
        # Scores
        "convictionScore": c.conviction_score or c.score or 0,
        "transitionScore": c.transition_score or 0,
        "qualityScore": c.quality_score or 0,
        "platformScore": c.platform_score or 0,
        "scoreBreakdown": c.score_breakdown or {},
        # Explanation
        "thesisBullets": explanation.get("thesisBullets") or [],
        "keyRisks": explanation.get("keyRisks") or [],
        "valuationBand": explanation.get("valuationBand") or {},
        "recommendedAction": explanation.get("recommendedAction") or "Research target",
        "transitionFactors": explanation.get("transitionFactors") or [],
        "qualityFactors": explanation.get("qualityFactors") or [],
        "platformFactors": explanation.get("platformFactors") or [],
        # Business data
        "googleRating": c.google_rating,
        "googleReviewCount": c.google_review_count,
        "domainAgeYears": c.domain_age_years,
        "signals": c.signals or [],
        "techStack": c.tech_stack or [],
        "sslValid": c.ssl_valid,
        "websiteActive": c.website_active,
        "hasFacebook": c.has_facebook,
        "hasInstagram": c.has_instagram,
        # Workflow
        "workflowStatus": c.workflow_status or "not_contacted",
        "workflowNotes": c.workflow_notes,
        "outreachDate": c.outreach_date,
        "lastContactDate": c.last_contact_date,
        # Content enrichment fields
        "isFamilyOwnedLikely": c.is_family_owned_likely,
        "offers247": c.offers_24_7,
        "serviceCountEstimated": c.service_count_estimated,
        "yearsInBusinessClaimed": c.years_in_business_claimed,
        "isRecruiting": c.is_recruiting,
        "technicianCountEstimated": c.technician_count_estimated,
        "servesCommercial": c.serves_commercial,
        "discoverySource": c.discovery_source,
        "contentEnriched": c.content_enriched or False,
        "councilAnalyzed": c.council_analyzed or False,
        # Meta
        "status": c.status,
        "rank": c.rank,
        "hasDossier": has_dossier,
        "hasMemo": has_memo,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("/feed")
async def deal_feed(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_conviction: Optional[int] = Query(None, ge=0, le=100),
    max_conviction: Optional[int] = Query(None, ge=0, le=100),
    state: Optional[str] = Query(None),
    workflow_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("conviction_score"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """Main deal feed -- ranked acquisition targets."""
    from sqlalchemy import func

    filters = []
    if min_conviction is not None:
        filters.append(Company.conviction_score >= min_conviction)
    if max_conviction is not None:
        filters.append(Company.conviction_score <= max_conviction)
    if state:
        filters.append(Company.state == state.upper())
    if workflow_status:
        filters.append(Company.workflow_status == workflow_status)
    if search:
        filters.append(or_(
            Company.name.ilike(f"%{search}%"),
            Company.city.ilike(f"%{search}%"),
            Company.state.ilike(f"%{search}%"),
        ))

    where = and_(*filters) if filters else True

    # Count
    cnt = (await db.execute(select(func.count(Company.id)).where(where))).scalar() or 0

    # Sort
    SORT_MAP = {
        "conviction_score": Company.conviction_score,
        "transition_score": Company.transition_score,
        "quality_score": Company.quality_score,
        "platform_score": Company.platform_score,
        "score": Company.score,
        "google_rating": Company.google_rating,
        "google_review_count": Company.google_review_count,
    }
    sort_col = SORT_MAP.get(sort_by, Company.conviction_score)
    order_fn = sort_col.desc() if sort_order != "asc" else sort_col.asc()

    res = await db.execute(
        select(Company).where(where).order_by(order_fn).offset(offset).limit(limit)
    )
    companies = res.scalars().all()

    # Check dossier / memo status
    company_ids = [c.id for c in companies]
    dossier_ids = set()
    memo_ids = set()
    if company_ids:
        d_res = await db.execute(select(Dossier.company_id).where(Dossier.company_id.in_(company_ids)))
        dossier_ids = {r[0] for r in d_res}
        m_res = await db.execute(select(Memo.company_id).where(Memo.company_id.in_(company_ids)))
        memo_ids = {r[0] for r in m_res}

    return {
        "deals": [
            company_to_deal(c, c.id in dossier_ids, c.id in memo_ids)
            for c in companies
        ],
        "total": cnt,
        "offset": offset,
        "limit": limit,
    }


@router.get("/top5")
async def top5_deals(db: AsyncSession = Depends(get_db)):
    """Today's Focus -- top 5 highest conviction targets."""
    res = await db.execute(
        select(Company)
        .where(Company.conviction_score > 0)
        .order_by(Company.conviction_score.desc())
        .limit(5)
    )
    companies = res.scalars().all()

    company_ids = [c.id for c in companies]
    dossier_ids = set()
    if company_ids:
        d_res = await db.execute(select(Dossier.company_id).where(Dossier.company_id.in_(company_ids)))
        dossier_ids = {r[0] for r in d_res}

    return {
        "topDeals": [company_to_deal(c, c.id in dossier_ids) for c in companies]
    }


@router.get("/tearsheet/{company_id}")
async def tearsheet(company_id: str, db: AsyncSession = Depends(get_db)):
    """Full tearsheet payload for decision pane."""
    from sqlalchemy.exc import NoResultFound

    res = await db.execute(select(Company).where(Company.id == company_id))
    c = res.scalar_one_or_none()
    if not c:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Company not found")

    d_res = await db.execute(select(Dossier).where(Dossier.company_id == company_id))
    dossier = d_res.scalar_one_or_none()

    m_res = await db.execute(
        select(Memo).where(Memo.company_id == company_id).order_by(Memo.version.desc())
    )
    memos = m_res.scalars().all()

    # Sort memos: council-v1 first, then by generated_at desc
    memos_sorted = sorted(
        memos,
        key=lambda m: (0 if getattr(m, "model_used", "") == "council-v1" else 1, -(getattr(m, "generated_at") or datetime.min).timestamp()),
    )

    # Workflow events
    from models import WorkflowEvent
    we_res = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.company_id == company_id)
        .order_by(WorkflowEvent.created_at.desc())
        .limit(20)
    )
    events = we_res.scalars().all()

    explanation = c.score_explanation or {}
    return {
        **company_to_deal(c, dossier is not None, len(memos_sorted) > 0),
        # Snapshot extras
        "email": c.email,
        "googlePlaceId": c.google_place_id,
        "websiteLoadTimeMs": c.website_load_time_ms,
        "websiteLastChecked": c.website_last_checked,
        "websiteOutdated": c.website_outdated,
        "rawGoogleData": None,  # suppress raw
        # Dossier
        "dossier": {
            "id": dossier.id,
            "content": dossier.content,
            "generatedAt": dossier.generated_at.isoformat() if dossier.generated_at else None,
            "modelUsed": dossier.model_used,
        } if dossier else None,
        # Memos
        "memos": [
            {
                "id": m.id,
                "version": m.version,
                "title": m.title,
                "status": m.status,
                "modelUsed": m.model_used,
                "updatedAt": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in memos_sorted
        ],
        # Workflow events
        "workflowEvents": [
            {
                "id": e.id,
                "fromStatus": e.from_status,
                "toStatus": e.to_status,
                "notes": e.notes,
                "createdAt": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
