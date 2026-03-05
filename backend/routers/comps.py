"""Comparable deals / valuation comps router."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import CompDeal
from auth import get_current_user, CurrentUser

router = APIRouter(prefix="/comps", tags=["comps"])


@router.get("")
async def list_comps(
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    res = await db.execute(select(CompDeal).order_by(CompDeal.deal_year.desc()))
    comps = res.scalars().all()
    return {
        "comps": [
            {
                "id": c.id,
                "dealName": c.deal_name,
                "dealYear": c.deal_year,
                "geography": c.geography,
                "dealType": c.deal_type,
                "revenueRange": c.revenue_range,
                "ebitdaMultipleLow": c.ebitda_multiple_low,
                "ebitdaMultipleHigh": c.ebitda_multiple_high,
                "sdeMultipleLow": c.sde_multiple_low,
                "sdeMultipleHigh": c.sde_multiple_high,
                "notes": c.notes,
                "source": c.source,
            }
            for c in comps
        ]
    }


async def seed_comps(db: AsyncSession):
    """Seed proxy HVAC comparable deals if table is empty."""
    existing = (await db.execute(select(CompDeal))).scalars().first()
    if existing:
        return

    comps_data = [
        dict(
            deal_name="Sun Belt HVAC Platform Acquisition",
            deal_year=2023,
            geography="Texas / Southeast US",
            deal_type="PE platform",
            revenue_range="$2M–$5M",
            ebitda_multiple_low=5.0,
            ebitda_multiple_high=8.0,
            sde_multiple_low=4.0,
            sde_multiple_high=6.5,
            notes="Residential-focused HVAC contractor, strong technician base",
            source="proxy",
        ),
        dict(
            deal_name="Phoenix Residential HVAC Add-On",
            deal_year=2023,
            geography="Phoenix, AZ",
            deal_type="PE add-on",
            revenue_range="$1M–$3M",
            ebitda_multiple_low=4.0,
            ebitda_multiple_high=7.0,
            sde_multiple_low=3.5,
            sde_multiple_high=5.5,
            notes="Owner-operator retirement sale; strong local reputation",
            source="proxy",
        ),
        dict(
            deal_name="Southeast HVAC Search Fund Acquisition",
            deal_year=2022,
            geography="Nashville, TN",
            deal_type="Search fund",
            revenue_range="$500K–$1.5M",
            ebitda_multiple_low=3.5,
            ebitda_multiple_high=6.0,
            sde_multiple_low=3.0,
            sde_multiple_high=5.0,
            notes="Micro-PE buyer, succession from retiring founder",
            source="proxy",
        ),
        dict(
            deal_name="Florida HVAC Bolt-On",
            deal_year=2024,
            geography="Orlando, FL",
            deal_type="Strategic add-on",
            revenue_range="$2M–$6M",
            ebitda_multiple_low=5.5,
            ebitda_multiple_high=9.0,
            sde_multiple_low=4.5,
            sde_multiple_high=7.0,
            notes="Commercial/residential mix; strong maintenance contract base",
            source="proxy",
        ),
        dict(
            deal_name="Mid-Market HVAC Roll-Up",
            deal_year=2022,
            geography="Southeast US (Multi-state)",
            deal_type="PE platform build",
            revenue_range="$5M–$15M",
            ebitda_multiple_low=6.0,
            ebitda_multiple_high=10.0,
            sde_multiple_low=5.0,
            sde_multiple_high=8.0,
            notes="Multi-location platform; includes service agreement annuity revenue",
            source="proxy",
        ),
        dict(
            deal_name="Micro-HVAC Sole Proprietor Acquisition",
            deal_year=2023,
            geography="Various US markets",
            deal_type="Independent buyer",
            revenue_range="$200K–$500K",
            ebitda_multiple_low=2.5,
            ebitda_multiple_high=4.5,
            sde_multiple_low=2.0,
            sde_multiple_high=3.5,
            notes="Sole proprietor retirement; cash-flow acquisition",
            source="proxy",
        ),
    ]

    for d in comps_data:
        db.add(CompDeal(**d))
    await db.commit()
