"""Dossiers API router."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, AsyncSessionLocal
from models import Dossier, Company
from sqlalchemy import update

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


@router.get("")
async def list_dossiers(
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    count_res = await db.execute(select(func.count(Dossier.id)))
    total = count_res.scalar() or 0

    offset = (page - 1) * limit
    res = await db.execute(
        select(Dossier, Company)
        .join(Company, Dossier.company_id == Company.id)
        .order_by(Company.score.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = res.all()

    return {
        "dossiers": [
            {
                "id": d.id,
                "companyId": d.company_id,
                "companyName": c.name,
                "companyCity": c.city,
                "companyState": c.state,
                "companyScore": c.score,
                "companyRank": c.rank,
                "content": d.content,
                "generatedAt": d.generated_at.isoformat() if d.generated_at else None,
                "modelUsed": d.model_used,
            }
            for d, c in rows
        ],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


@router.get("/{company_id}")
async def get_dossier(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Dossier).where(Dossier.company_id == company_id))
    dossier = res.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found")
    return {
        "id": dossier.id,
        "companyId": dossier.company_id,
        "content": dossier.content,
        "generatedAt": dossier.generated_at.isoformat() if dossier.generated_at else None,
        "modelUsed": dossier.model_used,
    }


@router.post("/{company_id}/generate")
async def generate_dossier(
    company_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Company).where(Company.id == company_id))
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    async def _generate():
        from agents.dossier_generator import DossierGenerator
        gen = DossierGenerator()
        company_dict = {
            "id": company.id,
            "name": company.name,
            "city": company.city,
            "state": company.state,
            "address": company.address,
            "phone": company.phone,
            "website": company.website,
            "google_rating": company.google_rating,
            "google_review_count": company.google_review_count,
            "domain_age_years": company.domain_age_years,
            "ssl_valid": company.ssl_valid,
            "tech_stack": company.tech_stack,
            "website_active": company.website_active,
            "has_facebook": company.has_facebook,
            "has_instagram": company.has_instagram,
            "signals": company.signals,
            "score": company.score,
            "score_breakdown": company.score_breakdown,
        }
        content = await gen.generate(company_dict)
        async with AsyncSessionLocal() as db2:
            ex_res = await db2.execute(select(Dossier).where(Dossier.company_id == company_id))
            existing = ex_res.scalar_one_or_none()
            if existing:
                existing.content = content
                existing.generated_at = datetime.utcnow()
            else:
                db2.add(Dossier(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    content=content,
                ))
            await db2.execute(
                update(Company).where(Company.id == company_id)
                .values(status="dossier_generated")
            )
            await db2.commit()

    background_tasks.add_task(_generate)
    return {"status": "generating", "company_id": company_id}
