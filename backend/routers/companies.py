"""Companies API router."""
import csv
import io
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import get_db
from models import Company, Dossier

router = APIRouter(prefix="/companies", tags=["companies"])


def company_to_dict(c: Company, include_dossier_flag: bool = True) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "address": c.address,
        "city": c.city,
        "state": c.state,
        "phone": c.phone,
        "website": c.website,
        "email": c.email,
        "googlePlaceId": c.google_place_id,
        "googleRating": c.google_rating,
        "googleReviewCount": c.google_review_count,
        "category": c.category,
        "domain": c.domain,
        "domainAgeYears": c.domain_age_years,
        "sslValid": c.ssl_valid,
        "sslExpiry": c.ssl_expiry,
        "techStack": c.tech_stack or [],
        "websiteActive": c.website_active,
        "websiteLoadTimeMs": c.website_load_time_ms,
        "websiteLastChecked": c.website_last_checked,
        "hasFacebook": c.has_facebook,
        "hasInstagram": c.has_instagram,
        "websiteOutdated": c.website_outdated,
        "signals": c.signals or [],
        "score": c.score or 0,
        "scoreBreakdown": c.score_breakdown or {},
        "status": c.status,
        "rank": c.rank,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
        "feedback": {
            "outcome": c.feedback_outcome,
            "notes": c.feedback_notes,
            "date": c.feedback_date,
        } if c.feedback_outcome else None,
    }


class FeedbackBody(BaseModel):
    outcome: str
    notes: Optional[str] = ""


VALID_SORT_COLS = {"score", "name", "rank", "google_rating", "google_review_count",
                   "domain_age_years", "created_at"}


@router.get("")
async def list_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("score"),
    sort_order: str = Query("desc"),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
    state: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if min_score is not None:
        filters.append(Company.score >= min_score)
    if max_score is not None:
        filters.append(Company.score <= max_score)
    if state:
        filters.append(Company.state == state.upper())
    if status:
        filters.append(Company.status == status)
    if search:
        filters.append(or_(
            Company.name.ilike(f"%{search}%"),
            Company.city.ilike(f"%{search}%"),
            Company.state.ilike(f"%{search}%"),
        ))

    where_clause = and_(*filters) if filters else True

    count_res = await db.execute(select(func.count(Company.id)).where(where_clause))
    total = count_res.scalar() or 0

    sort_col_name = sort_by if sort_by in VALID_SORT_COLS else "score"
    sort_col = getattr(Company, sort_col_name, Company.score)
    order_fn = sort_col.desc() if sort_order != "asc" else sort_col.asc()

    res = await db.execute(
        select(Company)
        .where(where_clause)
        .order_by(order_fn)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    companies = res.scalars().all()

    return {
        "companies": [company_to_dict(c) for c in companies],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


@router.get("/export/csv")
async def export_csv(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).order_by(Company.score.desc()))
    companies = res.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Rank", "Name", "City", "State", "Score", "Status",
        "Google Rating", "Reviews", "Domain Age (yrs)", "SSL Valid",
        "Website Active", "Tech Stack", "Phone", "Website",
        "Has Facebook", "Has Instagram", "Signals",
    ])
    for c in companies:
        signals_str = " | ".join(s.get("label", "") for s in (c.signals or []))
        writer.writerow([
            c.rank, c.name, c.city, c.state, c.score, c.status,
            c.google_rating, c.google_review_count,
            c.domain_age_years, c.ssl_valid, c.website_active,
            ", ".join(c.tech_stack or []),
            c.phone, c.website, c.has_facebook, c.has_instagram, signals_str,
        ])

    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hvac_acquisition_targets.csv"},
    )


@router.get("/export/json")
async def export_json(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).order_by(Company.score.desc()))
    companies = res.scalars().all()
    data = [company_to_dict(c) for c in companies]
    content = json.dumps(data, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=hvac_acquisition_targets.json"},
    )


@router.get("/{company_id}")
async def get_company(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    d_res = await db.execute(select(Dossier).where(Dossier.company_id == company_id))
    dossier = d_res.scalar_one_or_none()

    data = company_to_dict(company)
    data["hasDossier"] = dossier is not None
    if dossier:
        data["dossier"] = {
            "id": dossier.id,
            "content": dossier.content,
            "generatedAt": dossier.generated_at.isoformat() if dossier.generated_at else None,
            "modelUsed": dossier.model_used,
        }
    return data


@router.put("/{company_id}/feedback")
async def submit_feedback(
    company_id: str,
    body: FeedbackBody,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.feedback_outcome = body.outcome
    company.feedback_notes = body.notes
    company.feedback_date = datetime.utcnow().isoformat()
    await db.commit()
    return {"success": True, "outcome": body.outcome}
