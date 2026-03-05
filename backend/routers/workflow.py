"""Workflow / CRM router."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import get_db
from models import Company, WorkflowEvent
from auth import get_current_user, CurrentUser

router = APIRouter(prefix="/workflow", tags=["workflow"])

VALID_STATUSES = {
    "not_contacted", "contacted", "responded", "interested",
    "not_interested", "follow_up", "closed_lost", "closed_won",
}


class WorkflowUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    contact_date: Optional[str] = None


@router.put("/{company_id}")
async def update_workflow(
    company_id: str,
    body: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    res = await db.execute(
        select(Company).where(
            and_(Company.id == company_id, Company.user_id == user.user_id)
        )
    )
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")

    prev_status = c.workflow_status

    # Create audit event
    event = WorkflowEvent(
        company_id=company_id,
        from_status=prev_status,
        to_status=body.status,
        notes=body.notes,
    )
    db.add(event)

    # Update company
    c.workflow_status = body.status
    if body.notes:
        c.workflow_notes = body.notes
    if body.contact_date:
        c.outreach_date = body.contact_date
        c.last_contact_date = body.contact_date
    elif body.status in ("contacted", "responded", "interested"):
        c.last_contact_date = datetime.utcnow().isoformat()

    await db.commit()
    return {
        "success": True,
        "companyId": company_id,
        "previousStatus": prev_status,
        "newStatus": body.status,
    }


@router.get("/{company_id}/events")
async def get_workflow_events(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    # Verify company belongs to user before returning events
    c_res = await db.execute(
        select(Company).where(
            and_(Company.id == company_id, Company.user_id == user.user_id)
        )
    )
    company = c_res.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    res = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.company_id == company_id)
        .order_by(WorkflowEvent.created_at.desc())
    )
    events = res.scalars().all()
    return {
        "events": [
            {
                "id": e.id,
                "fromStatus": e.from_status,
                "toStatus": e.to_status,
                "notes": e.notes,
                "createdAt": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }
