"""Investment memo router."""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import get_db, AsyncSessionLocal
from models import Memo, Company

router = APIRouter(prefix="/memos", tags=["memos"])


class MemoUpdate(BaseModel):
    content: str
    title: Optional[str] = None
    status: Optional[str] = None


@router.get("/{company_id}")
async def get_memos(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Memo)
        .where(Memo.company_id == company_id)
        .order_by(Memo.version.desc())
    )
    memos = res.scalars().all()
    return {
        "memos": [
            {
                "id": m.id,
                "companyId": m.company_id,
                "version": m.version,
                "title": m.title,
                "content": m.content,
                "status": m.status,
                "generatedAt": m.generated_at.isoformat() if m.generated_at else None,
                "updatedAt": m.updated_at.isoformat() if m.updated_at else None,
                "modelUsed": m.model_used,
            }
            for m in memos
        ]
    }


@router.post("/{company_id}/generate")
async def generate_memo(
    company_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Company).where(Company.id == company_id))
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get next version number
    ver_res = await db.execute(
        select(Memo).where(Memo.company_id == company_id).order_by(Memo.version.desc()).limit(1)
    )
    existing = ver_res.scalar_one_or_none()
    next_version = (existing.version + 1) if existing else 1

    # Create placeholder
    memo_id = str(uuid.uuid4())
    placeholder = Memo(
        id=memo_id,
        company_id=company_id,
        version=next_version,
        title=f"Investment Memo v{next_version} -- {c.name}",
        content="*Generating...*",
        status="generating",
    )
    db.add(placeholder)
    await db.commit()

    async def _generate():
        explanation = c.score_explanation or {}
        thesis = explanation.get("thesisBullets") or []
        risks = explanation.get("keyRisks") or []
        valuation = explanation.get("valuationBand") or {}
        action = explanation.get("recommendedAction") or "Initial outreach"

        # Build memo without AI if no key configured
        content = _build_memo(c, thesis, risks, valuation, action, next_version)

        async with AsyncSessionLocal() as db2:
            res = await db2.execute(select(Memo).where(Memo.id == memo_id))
            memo = res.scalar_one_or_none()
            if memo:
                memo.content = content
                memo.status = "draft"
                memo.updated_at = datetime.utcnow()
            await db2.commit()

    background_tasks.add_task(_generate)
    return {"status": "generating", "memoId": memo_id, "version": next_version}


def _build_memo(c: Company, thesis: list, risks: list, valuation: dict, action: str, version: int) -> str:
    """Build an IC-memo style investment memo from available data."""
    rating_str = f"{c.google_rating}★" if c.google_rating else "N/A"
    review_str = f"{c.google_review_count}" if c.google_review_count else "N/A"
    domain_str = f"{c.domain_age_years:.0f} years" if c.domain_age_years else "N/A"
    city_state = f"{c.city or ''}, {c.state or ''}"
    val_low = valuation.get("low", 0)
    val_high = valuation.get("high", 0)
    multiple_range = valuation.get("multipleRange", "3.5x -- 5.5x SDE")
    val_basis = valuation.get("basis", "Proxy comps -- verify with seller financials")
    val_disclaimer = valuation.get("disclaimer", "Proxy estimate only. Verify with seller financials in diligence.")

    thesis_md = "\n".join(f"- {t}" for t in thesis) if thesis else "- See signals analysis"
    risks_md = "\n".join(f"- {r}" for r in risks) if risks else "- Standard owner-operator risks"

    return f"""
# Investment Memo v{version}
## {c.name}
**{city_state}** | {rating_str} ({review_str} reviews) | Domain age: {domain_str}

---

## Executive Summary

{c.name} is a {domain_str}-old HVAC contractor based in {city_state}. This memo outlines the acquisition thesis, underwriting assumptions, and recommended next steps for a potential acquisition by a PE platform, search fund, or independent buyer.

**Conviction Score:** {c.conviction_score or c.score}/100 | **Recommended Action:** {action}

---

## Why Now

{thesis_md}

---

## Underwriting Assumptions

| Metric | Estimate |
|--------|----------|
| Revenue estimate | Based on {review_str} Google reviews |
| Valuation range | ${val_low:,} -- ${val_high:,} |
| Multiple range | {multiple_range} |
| Acquisition type | Owner-operator succession |
| Deal structure | Asset purchase (typical for HVAC) |

**Valuation basis:** {val_basis}

*{val_disclaimer}*

---

## Upside Levers (90-Day Plan)

- **Review generation:** Implement systematic ask program -> target 4.5★+
- **Digital upgrade:** Modern website + SSL -> reduces lead cost
- **Maintenance contracts:** Convert 1-time customers to recurring service agreements
- **Technician leverage:** Add 1--2 technicians to increase capacity without owner dependency
- **Geographic expansion:** Use existing brand to open adjacent zip codes

---

## Key Risks & Mitigations

{risks_md}

**Mitigations:**
- Owner transition period: negotiate 12--24 month earnout with training component
- Key man risk: cross-train staff; build documented playbooks before close
- Customer concentration: review top-10 customer revenue concentration in diligence

---

## Diligence Checklist

- [ ] 3 years P&L + tax returns
- [ ] Customer list + revenue breakdown (residential vs. commercial)
- [ ] Technician headcount + license status
- [ ] Maintenance contract book + renewal rates
- [ ] Equipment + vehicle inventory
- [ ] Supplier relationships + pricing agreements
- [ ] Pending customer complaints or warranty claims
- [ ] Owner compensation normalization for SDE calculation

---

## Recommended Next Step

**{action}**

See Outreach tab for personalized contact approach.

---

*Generated by HVAC Intel Deal Engine | {c.name} | v{version}*
"""


@router.put("/{memo_id}")
async def update_memo(
    memo_id: str,
    body: MemoUpdate,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Memo).where(Memo.id == memo_id))
    memo = res.scalar_one_or_none()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")

    memo.content = body.content
    if body.title:
        memo.title = body.title
    if body.status:
        memo.status = body.status
    memo.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "memoId": memo_id}
