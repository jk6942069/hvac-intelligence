"""
FastAPI auth dependency — verifies Supabase JWT and loads user from DB.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import User

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: str
    email: str
    plan: str
    scans_used_this_month: int


def _decode_jwt(token: str, secret: str) -> dict:
    """Decode and verify a Supabase JWT. Raises HTTP 401 on any error."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
        return payload
    except JWTError as e:
        logger.debug(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _upsert_user(db: AsyncSession, user_id: str, email: str) -> User:
    """
    Ensure user row exists in our DB. Creates it on first login.
    Resets scan counter if more than 30 days since last reset.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(id=user_id, email=email, plan="starter")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Monthly scan counter reset
        now = datetime.utcnow()
        if user.scans_reset_at is None or (now - user.scans_reset_at) > timedelta(days=30):
            user.scans_used_this_month = 0
            user.scans_reset_at = now
            await db.commit()

    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    FastAPI dependency — validates JWT and returns CurrentUser.
    Raises 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = settings.supabase_jwt_secret
    if not secret:
        # Dev mode: accept any well-formed JWT with a known test secret
        # ONLY activates when SUPABASE_JWT_SECRET is unset
        logger.warning("SUPABASE_JWT_SECRET not set — JWT verification disabled (dev mode)")
        secret = "dev-secret-not-for-production-use!!"

    payload = _decode_jwt(credentials.credentials, secret)
    user_id: str = payload.get("sub", "")
    email: str = payload.get("email", "")

    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    user = await _upsert_user(db, user_id, email)
    return CurrentUser(
        user_id=user.id,
        email=user.email or email,
        plan=user.plan,
        scans_used_this_month=user.scans_used_this_month,
    )


async def get_current_user_ws(token: str, db: AsyncSession) -> CurrentUser:
    """
    WebSocket variant — token passed as query param (WebSockets can't send headers).
    """
    secret = settings.supabase_jwt_secret or "dev-secret-not-for-production-use!!"
    payload = _decode_jwt(token, secret)
    user_id = payload.get("sub", "")
    email = payload.get("email", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")
    user = await _upsert_user(db, user_id, email)
    return CurrentUser(
        user_id=user.id,
        email=user.email or email,
        plan=user.plan,
        scans_used_this_month=user.scans_used_this_month,
    )
