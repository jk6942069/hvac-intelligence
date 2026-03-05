"""Stripe billing router -- Checkout, Webhook, Portal, Status."""
import json
import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import CurrentUser, get_current_user
from config import settings
from database import get_db, AsyncSessionLocal
from models import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

PLAN_DISPLAY = {
    "starter": {"name": "Starter", "price": "$49/month", "scans": "10 scans/month"},
    "professional": {"name": "Professional", "price": "$149/month", "scans": "Unlimited"},
    "enterprise": {"name": "Enterprise", "price": "Contact sales", "scans": "Unlimited + priority"},
}


def _init_stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe not configured -- set STRIPE_SECRET_KEY")
    stripe.api_key = settings.stripe_secret_key


@router.post("/create-checkout")
async def create_checkout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session and return the redirect URL."""
    _init_stripe()
    body = await request.json()
    plan = body.get("plan", "professional")

    price_id = (
        settings.stripe_starter_price_id if plan == "starter"
        else settings.stripe_pro_price_id
    )
    if not price_id:
        raise HTTPException(400, f"Price ID not configured for plan: {plan}")

    # Get or create Stripe customer
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    customer_id = db_user.stripe_customer_id if db_user else None

    if not customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.user_id})
        customer_id = customer.id
        await db.execute(
            sql_update(User).where(User.id == user.user_id).values(stripe_customer_id=customer_id)
        )
        await db.commit()

    origin = str(request.base_url).rstrip("/")
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{origin}/settings?billing=success",
        cancel_url=f"{origin}/settings?billing=cancel",
        metadata={"user_id": user.user_id, "plan": plan},
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events. No JWT auth -- uses Stripe signature verification."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except Exception:
            raise HTTPException(400, "Invalid webhook signature")
    else:
        # STRIPE_WEBHOOK_SECRET not set — accepting unverified payload.
        # This is acceptable in local dev only. In production ALWAYS set STRIPE_WEBHOOK_SECRET.
        logger.warning(
            "STRIPE_WEBHOOK_SECRET not set — processing webhook WITHOUT signature verification "
            "(dev mode only). Set STRIPE_WEBHOOK_SECRET in production."
        )
        event = json.loads(payload)

    event_type = event.get("type", "")
    logger.info(f"Stripe webhook: {event_type}")

    async with AsyncSessionLocal() as db:
        if event_type == "checkout.session.completed":
            session_obj = event["data"]["object"]
            user_id = session_obj.get("metadata", {}).get("user_id")
            plan = session_obj.get("metadata", {}).get("plan", "professional")
            customer_id = session_obj.get("customer")
            subscription_id = session_obj.get("subscription")
            if user_id:
                await db.execute(
                    sql_update(User).where(User.id == user_id).values(
                        plan=plan,
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=subscription_id,
                    )
                )
                await db.commit()
                logger.info(f"User {user_id} upgraded to {plan}")

        elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            sub = event["data"]["object"]
            customer_id = sub.get("customer")
            if event_type == "customer.subscription.deleted":
                new_plan = "starter"
            else:
                items = sub.get("items", {}).get("data", [])
                price_id = items[0]["price"]["id"] if items else ""
                price_map = {
                    settings.stripe_starter_price_id: "starter",
                    settings.stripe_pro_price_id: "professional",
                }
                new_plan = price_map.get(price_id, "starter")

            if customer_id:
                await db.execute(
                    sql_update(User)
                    .where(User.stripe_customer_id == customer_id)
                    .values(plan=new_plan)
                )
                await db.commit()
                logger.info(f"Customer {customer_id} plan updated to {new_plan}")

    return {"received": True}


@router.post("/portal")
async def billing_portal(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing subscription."""
    _init_stripe()
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if not db_user or not db_user.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer found. Subscribe first.")

    origin = str(request.base_url).rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=db_user.stripe_customer_id,
        return_url=f"{origin}/settings",
    )
    return {"url": session.url}


@router.get("/status")
async def billing_status(user: CurrentUser = Depends(get_current_user)):
    """Return current plan and usage for the Settings page."""
    plan_info = PLAN_DISPLAY.get(user.plan, PLAN_DISPLAY["starter"])
    limit = 10 if user.plan == "starter" else None
    return {
        "plan": user.plan,
        "planDisplay": plan_info,
        "scansUsed": user.scans_used_this_month,
        "scansLimit": limit,
        "scansRemaining": max(0, limit - user.scans_used_this_month) if limit else None,
    }
