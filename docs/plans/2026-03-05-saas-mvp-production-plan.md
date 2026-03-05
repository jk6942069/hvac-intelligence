# SaaS MVP Production Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Supabase Auth, multi-tenant PostgreSQL, and Stripe billing to the existing HVAC Intelligence Engine so it can be deployed as a revenue-ready SaaS.

**Architecture:** JWT issued by Supabase is verified by FastAPI's `get_current_user` dependency; every data-touching query filters by `user_id`; Stripe Checkout + Customer Portal handle all billing; Alembic manages production schema; SQLite + `init_db()` continue to serve tests.

**Tech Stack:** FastAPI + SQLAlchemy async + asyncpg (prod) / aiosqlite (test), Alembic, python-jose[cryptography], stripe, @supabase/supabase-js, React + Vite + Tailwind.

---

## Task 1: Backend dependencies + config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Create: `backend/.env.example`

**Step 1: Add missing packages to requirements.txt**

Append these lines to `backend/requirements.txt`:
```
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
stripe==8.7.0
```

**Step 2: Run install to verify no conflicts**

```bash
cd backend && pip install alembic==1.13.1 asyncpg==0.29.0 psycopg2-binary==2.9.9 "python-jose[cryptography]==3.3.0" stripe==8.7.0
```
Expected: all packages install without dependency errors.

**Step 3: Update config.py**

Add these fields to the `Settings` class (after the existing `database_url` line):

```python
import os
# ... existing imports ...

class Settings(BaseSettings):
    # ... existing fields ...

    # Database — reads from env in production, defaults to SQLite for local dev/tests
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./hvac_intel.db")

    # Supabase Auth
    supabase_jwt_secret: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_starter_price_id: str = ""
    stripe_pro_price_id: str = ""

    # CORS — include Vercel domain when set
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    cors_origin_prod: str = ""   # e.g. "https://hvac-intel.vercel.app"
```

Also change the `database_url` default declaration to use `os.getenv` (important: pydantic-settings already reads env vars, but we also want tests to be able to set `TEST_DATABASE_URL` and have the engine pick it up — handled in Task 2).

**Step 4: Create .env.example**

```bash
# backend/.env.example

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Supabase
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...

# CORS (set to your Vercel domain in production)
CORS_ORIGIN_PROD=https://your-app.vercel.app
```

**Step 5: Commit**

```bash
cd backend
git add requirements.txt config.py .env.example
git commit -m "feat: add alembic/asyncpg/jose/stripe deps + config fields for SaaS"
```

---

## Task 2: Fix database.py for dual-driver support

**Files:**
- Modify: `backend/database.py`

The current `connect_args={"check_same_thread": False}` is SQLite-specific and crashes asyncpg. We fix this by inspecting the URL before creating the engine.

**Step 1: Write the failing test**

Create `backend/tests/test_database_engine.py`:

```python
"""Test that database.py correctly configures engine for SQLite vs PostgreSQL URLs."""
import pytest
import os


def test_sqlite_url_accepted():
    """SQLite URL should not raise on engine creation."""
    os.environ.pop("DATABASE_URL", None)  # ensure default SQLite
    # Re-import to pick up env
    import importlib
    import database
    importlib.reload(database)
    assert "sqlite" in str(database.engine.url)


def test_database_url_env_overrides_default(monkeypatch):
    """DATABASE_URL env var should override the SQLite default."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test_override.db")
    import importlib
    import config
    importlib.reload(config)
    import database
    importlib.reload(database)
    assert "test_override" in str(database.engine.url)
```

**Step 2: Run to confirm it passes already (engine exists)**

```bash
cd backend && python -m pytest tests/test_database_engine.py -v
```
Expected: both tests pass (engine already exists; we just confirm SQLite works).

**Step 3: Update database.py**

Replace the engine creation block:

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings


def _make_engine():
    url = os.getenv("DATABASE_URL", settings.database_url)
    is_sqlite = url.startswith("sqlite")
    kwargs = {}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # asyncpg pool sizing for Railway free tier
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_async_engine(url, echo=settings.debug, **kwargs)


engine = _make_engine()

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def migrate_db():
    """
    Idempotent column migrations for SQLite dev/test only.
    In production, Alembic handles migrations.
    """
    from sqlalchemy import text
    url = str(engine.url)
    if "sqlite" not in url:
        return   # production: Alembic manages schema

    migrations = [
        # v2 scoring columns
        "ALTER TABLE companies ADD COLUMN transition_score INTEGER DEFAULT 0",
        "ALTER TABLE companies ADD COLUMN quality_score INTEGER DEFAULT 0",
        "ALTER TABLE companies ADD COLUMN platform_score INTEGER DEFAULT 0",
        "ALTER TABLE companies ADD COLUMN conviction_score INTEGER DEFAULT 0",
        "ALTER TABLE companies ADD COLUMN score_explanation TEXT",
        # CRM workflow columns
        "ALTER TABLE companies ADD COLUMN workflow_status VARCHAR DEFAULT 'not_contacted'",
        "ALTER TABLE companies ADD COLUMN workflow_notes TEXT",
        "ALTER TABLE companies ADD COLUMN outreach_date VARCHAR",
        "ALTER TABLE companies ADD COLUMN last_contact_date VARCHAR",
        # Content enrichment + council tracking columns (v3)
        "ALTER TABLE companies ADD COLUMN is_family_owned_likely BOOLEAN",
        "ALTER TABLE companies ADD COLUMN offers_24_7 BOOLEAN",
        "ALTER TABLE companies ADD COLUMN service_count_estimated INTEGER",
        "ALTER TABLE companies ADD COLUMN years_in_business_claimed INTEGER",
        "ALTER TABLE companies ADD COLUMN is_recruiting BOOLEAN",
        "ALTER TABLE companies ADD COLUMN technician_count_estimated INTEGER",
        "ALTER TABLE companies ADD COLUMN serves_commercial BOOLEAN",
        "ALTER TABLE companies ADD COLUMN discovery_source VARCHAR",
        "ALTER TABLE companies ADD COLUMN content_enriched BOOLEAN DEFAULT FALSE",
        "ALTER TABLE companies ADD COLUMN council_analyzed BOOLEAN DEFAULT FALSE",
        # SaaS multi-tenancy columns
        "ALTER TABLE companies ADD COLUMN user_id TEXT",
        "ALTER TABLE pipeline_runs ADD COLUMN user_id TEXT",
        "ALTER TABLE pipeline_runs ADD COLUMN cities TEXT",
        "ALTER TABLE memos ADD COLUMN user_id TEXT",
    ]

    async with engine.connect() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                await conn.commit()
            except Exception as e:
                if "duplicate column name" not in str(e).lower():
                    raise

        # Workflow state migration
        try:
            await conn.execute(text("""
                UPDATE companies SET workflow_status = CASE workflow_status
                    WHEN 'responded'      THEN 'contacted'
                    WHEN 'interested'     THEN 'conversation_started'
                    WHEN 'follow_up'      THEN 'conversation_started'
                    WHEN 'closed_won'     THEN 'loi_considered'
                    WHEN 'closed_lost'    THEN 'passed'
                    WHEN 'not_interested' THEN 'passed'
                    ELSE workflow_status
                END
                WHERE workflow_status IN (
                    'responded','interested','follow_up',
                    'closed_won','closed_lost','not_interested'
                )
            """))
            await conn.commit()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Workflow migration: {e}")
```

**Step 4: Run tests again**

```bash
cd backend && python -m pytest tests/test_database_engine.py -v
```
Expected: PASS.

**Step 5: Run full test suite to confirm nothing broke**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: same pass count as before (existing tests unaffected).

**Step 6: Commit**

```bash
cd backend
git add database.py tests/test_database_engine.py
git commit -m "fix: conditional connect_args for SQLite vs PostgreSQL engine"
```

---

## Task 3: Update models.py — users table + user_id columns

**Files:**
- Modify: `backend/models.py`

**Step 1: Write the failing test**

Create `backend/tests/test_models_saas.py`:

```python
"""Verify new SaaS models have correct fields."""
from models import User, Company, PipelineRun, Memo


def test_user_model_has_plan_field():
    u = User(id="test-uid", email="test@example.com")
    assert u.plan == "starter"
    assert u.scans_used_this_month == 0


def test_company_has_user_id():
    assert hasattr(Company, "user_id")


def test_pipeline_run_has_user_id_and_cities():
    assert hasattr(PipelineRun, "user_id")
    assert hasattr(PipelineRun, "cities")


def test_memo_has_user_id():
    assert hasattr(Memo, "user_id")
```

**Step 2: Run to confirm FAIL**

```bash
cd backend && python -m pytest tests/test_models_saas.py -v
```
Expected: FAIL — `cannot import name 'User' from 'models'`

**Step 3: Update models.py**

Add `User` model at the top (after imports):

```python
class User(Base):
    """App-level user — bridges Supabase auth.uid() with plan/billing state."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)           # = Supabase auth.uid()
    email = Column(String)                           # cached copy from JWT
    plan = Column(String, nullable=False, default="starter")  # starter / professional / enterprise
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)
    scans_used_this_month = Column(Integer, nullable=False, default=0)
    scans_reset_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
```

Add `user_id` to `Company` (after `raw_google_data` line, and remove `unique=True` from `google_place_id`):

```python
    # Change this line:
    google_place_id = Column(String, index=True)   # removed unique=True — two users can have same company
    # ...existing fields...
    # Add at end of Company class (before closing):
    user_id = Column(String, index=True)  # FK to users.id — set on insert, nullable for legacy data
```

Add `user_id` and `cities` JSON to `PipelineRun`:

```python
    # Add to PipelineRun class:
    user_id = Column(String, index=True)
    cities = Column(JSON)  # list of ["City, ST"] strings
```

Add `user_id` to `Memo`:

```python
    # Add to Memo class:
    user_id = Column(String, index=True)
```

**Step 4: Run test to verify PASS**

```bash
cd backend && python -m pytest tests/test_models_saas.py -v
```
Expected: all 4 tests PASS.

**Step 5: Run full suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 6: Commit**

```bash
cd backend
git add models.py tests/test_models_saas.py
git commit -m "feat: add User model and user_id columns for multi-tenancy"
```

---

## Task 4: Alembic setup + production migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/` directory (via alembic init)
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_saas_schema.py`

**Step 1: Initialize Alembic**

```bash
cd backend && alembic init alembic
```
Expected: creates `alembic/` directory and `alembic.ini`.

**Step 2: Update alembic.ini to use env var**

In `alembic.ini`, change:
```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```
to:
```ini
sqlalchemy.url = %(DATABASE_URL)s
```

**Step 3: Update alembic/env.py for async + models**

Replace the contents of `backend/alembic/env.py`:

```python
import asyncio
import os
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Import all models so Alembic can detect them
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Base  # noqa: F401 — imports all model classes

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./hvac_intel.db")


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = get_url()
    connectable = create_async_engine(url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 4: Create first migration file**

Create `backend/alembic/versions/001_initial_saas_schema.py`:

```python
"""Initial SaaS schema: users table + user_id columns + indexes.

Revision ID: 001
Revises:
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=False, server_default='starter'),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('scans_used_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scans_reset_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add user_id to companies
    op.add_column('companies', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_companies_user_conviction', 'companies', ['user_id', 'conviction_score'])
    op.create_foreign_key('fk_companies_user_id', 'companies', 'users', ['user_id'], ['id'])

    # Add user_id + cities to pipeline_runs
    op.add_column('pipeline_runs', sa.Column('user_id', sa.String(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('cities', sa.JSON(), nullable=True))
    op.create_index('ix_pipeline_runs_user_created', 'pipeline_runs', ['user_id', 'started_at'])
    op.create_foreign_key('fk_pipeline_runs_user_id', 'pipeline_runs', 'users', ['user_id'], ['id'])

    # Add user_id to memos
    op.add_column('memos', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_memos_user_id', 'memos', ['user_id'])
    op.create_foreign_key('fk_memos_user_id', 'memos', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_memos_user_id', 'memos', type_='foreignkey')
    op.drop_index('ix_memos_user_id', 'memos')
    op.drop_column('memos', 'user_id')

    op.drop_constraint('fk_pipeline_runs_user_id', 'pipeline_runs', type_='foreignkey')
    op.drop_index('ix_pipeline_runs_user_created', 'pipeline_runs')
    op.drop_column('pipeline_runs', 'cities')
    op.drop_column('pipeline_runs', 'user_id')

    op.drop_constraint('fk_companies_user_id', 'companies', type_='foreignkey')
    op.drop_index('ix_companies_user_conviction', 'companies')
    op.drop_column('companies', 'user_id')

    op.drop_table('users')
```

**Step 5: Verify Alembic can generate SQL (offline, no DB needed)**

```bash
cd backend && DATABASE_URL="postgresql+asyncpg://x:x@localhost/x" alembic upgrade 001 --sql 2>&1 | head -40
```
Expected: prints SQL DDL statements (CREATE TABLE users, ALTER TABLE companies ADD COLUMN user_id, etc.). No errors.

**Step 6: Commit**

```bash
cd backend
git add alembic.ini alembic/ requirements.txt
git commit -m "feat: alembic setup + 001 migration (users table, user_id columns, indexes)"
```

---

## Task 5: backend/auth.py — JWT verification + CurrentUser dependency

**Files:**
- Create: `backend/auth.py`
- Create: `backend/tests/test_auth.py`

**Step 1: Write the failing test**

Create `backend/tests/test_auth.py`:

```python
"""Tests for JWT verification and CurrentUser dependency."""
import pytest
import time
from jose import jwt
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException


def make_token(secret: str, sub: str = "user-123", email: str = "test@example.com") -> str:
    """Create a valid Supabase-style JWT."""
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "role": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_valid_token():
    """Valid token with correct secret should decode without error."""
    secret = "test-secret-32-chars-minimum-ok!"
    token = make_token(secret)
    from auth import _decode_jwt
    payload = _decode_jwt(token, secret)
    assert payload["sub"] == "user-123"
    assert payload["email"] == "test@example.com"


def test_decode_invalid_token_raises():
    """Invalid token should raise HTTPException 401."""
    from auth import _decode_jwt
    with pytest.raises(HTTPException) as exc:
        _decode_jwt("not.a.valid.token", "secret")
    assert exc.value.status_code == 401


def test_decode_wrong_secret_raises():
    """Token signed with wrong secret raises 401."""
    token = make_token("correct-secret-32-chars-minimum!")
    from auth import _decode_jwt
    with pytest.raises(HTTPException) as exc:
        _decode_jwt(token, "wrong-secret-32-chars-minimum-no")
    assert exc.value.status_code == 401


def test_current_user_dataclass():
    """CurrentUser holds expected fields."""
    from auth import CurrentUser
    u = CurrentUser(user_id="abc", email="x@y.com", plan="starter", scans_used_this_month=3)
    assert u.user_id == "abc"
    assert u.plan == "starter"
```

**Step 2: Run to confirm FAIL**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```
Expected: FAIL — `cannot import name '_decode_jwt' from 'auth'`

**Step 3: Create backend/auth.py**

```python
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
    Ensure user row exists. Creates it on first login.
    Resets scan counter if > 30 days since last reset.
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
        # This only activates when SUPABASE_JWT_SECRET is unset
        logger.warning("SUPABASE_JWT_SECRET not set — using insecure dev mode")
        secret = "dev-secret-not-for-production-use!"

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
    WebSocket variant — token passed as query param (no Authorization header possible).
    """
    secret = settings.supabase_jwt_secret or "dev-secret-not-for-production-use!"
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
```

**Step 4: Run test to confirm PASS**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```
Expected: all 4 tests PASS.

**Step 5: Run full suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 6: Commit**

```bash
cd backend
git add auth.py tests/test_auth.py
git commit -m "feat: auth.py with JWT verification and CurrentUser dependency"
```

---

## Task 6: Protect routes + multi-tenant filtering

**Files:**
- Modify: `backend/routers/companies.py`
- Modify: `backend/routers/dealdesk.py`
- Modify: `backend/routers/pipeline.py`
- Modify: `backend/routers/dossiers.py`
- Modify: `backend/routers/memos.py`
- Modify: `backend/routers/workflow.py`

**Step 1: Write the failing test (API-level auth)**

Create `backend/tests/test_auth_routes.py`:

```python
"""Verify protected routes reject unauthenticated requests."""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.anyio
async def test_companies_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/companies")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_dealdesk_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/dealdesk/feed")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_pipeline_run_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/pipeline/run", json={})
    assert r.status_code == 401


@pytest.mark.anyio
async def test_health_is_public():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health")
    assert r.status_code == 200
```

Add to `backend/tests/conftest.py`:
```python
import pytest

# Required for anyio-based async tests
pytest_plugins = ('anyio',)
```

Install test deps:
```bash
pip install anyio[trio] pytest-anyio httpx
```

**Step 2: Run to confirm FAIL**

```bash
cd backend && python -m pytest tests/test_auth_routes.py -v
```
Expected: FAIL — routes return 200 (unauthenticated access allowed currently).

**Step 3: Add auth to companies.py**

At top of `backend/routers/companies.py`, add import:
```python
from auth import get_current_user, CurrentUser
```

For every `@router.get` / `@router.post` / `@router.put` / `@router.delete` that touches Company data, add the dependency and filter:

```python
# Example: list companies
@router.get("")
async def list_companies(
    # ... existing params ...
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),   # ADD THIS
):
    # Change ALL .where() or .filter() calls to add user_id filter:
    # Before: select(Company).where(...)
    # After:  select(Company).where(Company.user_id == user.user_id, ...)
```

Apply the same pattern to:
- `GET /companies` — add `.where(Company.user_id == user.user_id)` to main query
- `GET /companies/{id}` — add `.where(Company.id == company_id, Company.user_id == user.user_id)`
- `PUT /companies/{id}/feedback` — add user_id filter
- `GET /companies/export` — add user_id filter

**Step 4: Add auth to dealdesk.py**

Same pattern — add `user: CurrentUser = Depends(get_current_user)` to all routes and filter `Company.user_id == user.user_id` in all queries.

**Step 5: Add auth to pipeline.py**

```python
from auth import get_current_user, CurrentUser, get_current_user_ws
from database import AsyncSessionLocal

# POST /run — add user dependency + pass user_id to orchestrator
@router.post("/run")
async def start_pipeline(
    config: RunConfig,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    # ... existing code ...
    async def _run():
        await orch.run(
            cities=target_cities,
            max_companies=config.max_companies,
            generate_dossiers_for_top=config.generate_dossiers_for_top,
            run_id=run_id,
            user_id=user.user_id,    # ADD THIS
        )
    # ...

# GET /status — add auth
@router.get("/status")
async def pipeline_status(user: CurrentUser = Depends(get_current_user)):
    # Filter PipelineRun by user_id
    res = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.user_id == user.user_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )

# GET /history — add auth + filter
@router.get("/history")
async def pipeline_history(user: CurrentUser = Depends(get_current_user)):
    # Filter by user.user_id

# WebSocket — accept token as query param
@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = ""):
    await websocket.accept()
    if token:
        try:
            async with AsyncSessionLocal() as db:
                await get_current_user_ws(token, db)
        except Exception:
            await websocket.close(code=4001)
            return
    _ws_connections.append(websocket)
    # ... rest unchanged ...
```

**Step 6: Add auth to dossiers.py, memos.py, workflow.py**

Same pattern for each:
- Import `get_current_user, CurrentUser` from `auth`
- Add `user: CurrentUser = Depends(get_current_user)` to all route functions
- Filter queries by `user_id` where Company or Memo is accessed

**Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_auth_routes.py -v
```
Expected: all 4 tests PASS.

**Step 8: Run full suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions in existing tests (they don't call protected HTTP routes).

**Step 9: Commit**

```bash
cd backend
git add routers/companies.py routers/dealdesk.py routers/pipeline.py \
        routers/dossiers.py routers/memos.py routers/workflow.py \
        tests/test_auth_routes.py tests/conftest.py
git commit -m "feat: protect all data routes with JWT auth + multi-tenant user_id filtering"
```

---

## Task 7: Rate limiting + orchestrator user_id threading

**Files:**
- Modify: `backend/routers/pipeline.py`
- Modify: `backend/agents/orchestrator.py`

**Step 1: Write failing test for rate limiting**

Create `backend/tests/test_rate_limit.py`:

```python
"""Test scan quota enforcement."""
import pytest
from auth import CurrentUser
from fastapi import HTTPException


def make_user(plan: str, scans_used: int) -> CurrentUser:
    return CurrentUser(
        user_id="uid-1",
        email="x@y.com",
        plan=plan,
        scans_used_this_month=scans_used,
    )


def test_starter_within_limit_passes():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("starter", 5))  # should not raise


def test_starter_at_limit_raises_429():
    from routers.pipeline import check_scan_quota
    with pytest.raises(HTTPException) as exc:
        check_scan_quota(make_user("starter", 10))
    assert exc.value.status_code == 429


def test_professional_unlimited():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("professional", 9999))  # should not raise


def test_enterprise_unlimited():
    from routers.pipeline import check_scan_quota
    check_scan_quota(make_user("enterprise", 9999))  # should not raise
```

**Step 2: Run to confirm FAIL**

```bash
cd backend && python -m pytest tests/test_rate_limit.py -v
```
Expected: FAIL — `cannot import name 'check_scan_quota' from 'routers.pipeline'`

**Step 3: Add rate limiting to pipeline.py**

At top of `backend/routers/pipeline.py`, add:

```python
from auth import CurrentUser, get_current_user
from models import User
from sqlalchemy import update as sql_update

PLAN_LIMITS = {
    "starter": 10,
    "professional": None,   # unlimited
    "enterprise": None,     # unlimited
}


def check_scan_quota(user: CurrentUser):
    """Raises HTTP 429 if user has exceeded their monthly scan quota."""
    limit = PLAN_LIMITS.get(user.plan)
    if limit is not None and user.scans_used_this_month >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly scan limit of {limit} reached. Upgrade to Professional.",
        )
```

In the `start_pipeline` route, after `check_scan_quota(user)`, increment the counter:

```python
@router.post("/run")
async def start_pipeline(config: RunConfig, background_tasks: BackgroundTasks,
                         user: CurrentUser = Depends(get_current_user)):
    check_scan_quota(user)

    orch = _get_orchestrator()
    if orch.is_running:
        return {"status": "already_running", "run_id": orch.current_run_id}

    # Increment scan counter
    async with AsyncSessionLocal() as db:
        await db.execute(
            sql_update(User)
            .where(User.id == user.user_id)
            .values(scans_used_this_month=User.scans_used_this_month + 1)
        )
        await db.commit()

    # ... rest of existing code ...
```

**Step 4: Update orchestrator to accept user_id**

In `backend/agents/orchestrator.py`, change `run()` signature:

```python
async def run(
    self,
    cities: list[tuple[str, str]] = None,
    max_companies: int = 200,
    generate_dossiers_for_top: int = 20,
    run_id: str = None,
    user_id: str = None,   # ADD THIS
) -> str:
```

In the `PipelineRun` creation block:
```python
pr = PipelineRun(
    id=run_id,
    status="running",
    config_json={"max_companies": max_companies},
    user_id=user_id,   # ADD THIS
    cities=cities,     # ADD THIS (store as list for history)
)
```

In Stage 1 (scout), after `companies_raw` is collected, stamp each with `user_id`:
```python
# After companies_raw is populated (both OSM and Firecrawl paths):
if user_id:
    for c in companies_raw:
        c["user_id"] = user_id
```

In the company upsert/insert code (wherever `db.add(company)` or bulk insert happens), ensure `user_id` is set on the `Company` object before insert. Find the line where `Company(...)` is constructed and add `user_id=user_id` if not already there.

**Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_rate_limit.py -v
```
Expected: all 4 tests PASS.

**Step 6: Run full suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 7: Commit**

```bash
cd backend
git add routers/pipeline.py agents/orchestrator.py tests/test_rate_limit.py
git commit -m "feat: scan quota rate limiting + orchestrator user_id threading"
```

---

## Task 8: Stripe billing router

**Files:**
- Create: `backend/routers/billing.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_billing.py`

**Step 1: Write failing test**

Create `backend/tests/test_billing.py`:

```python
"""Test billing endpoint structure (mocked Stripe)."""
import pytest
from unittest.mock import patch, MagicMock


def test_plan_limits_defined():
    """Billing status endpoint requires plan to be readable."""
    from routers.billing import PLAN_DISPLAY
    assert "starter" in PLAN_DISPLAY
    assert "professional" in PLAN_DISPLAY


def test_billing_router_registered():
    """Billing router should be importable without errors."""
    from routers.billing import router
    routes = [r.path for r in router.routes]
    assert "/create-checkout" in routes
    assert "/webhook" in routes
    assert "/portal" in routes
    assert "/status" in routes
```

**Step 2: Run to confirm FAIL**

```bash
cd backend && python -m pytest tests/test_billing.py -v
```
Expected: FAIL — `cannot import name 'PLAN_DISPLAY' from 'routers.billing'`

**Step 3: Create backend/routers/billing.py**

```python
"""Stripe billing router — Checkout, Webhook, Portal, Status."""
import logging
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import CurrentUser, get_current_user
from config import settings
from database import get_db
from models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

PLAN_DISPLAY = {
    "starter": {"name": "Starter", "price": "$49/month", "scans": "10 scans/month"},
    "professional": {"name": "Professional", "price": "$149/month", "scans": "Unlimited"},
    "enterprise": {"name": "Enterprise", "price": "Contact sales", "scans": "Unlimited + priority"},
}

PRICE_TO_PLAN = {}  # populated lazily from env vars


def _get_stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Stripe not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _build_price_map():
    return {
        settings.stripe_starter_price_id: "starter",
        settings.stripe_pro_price_id: "professional",
    }


@router.post("/create-checkout")
async def create_checkout(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session and return the URL."""
    body = await request.json()
    plan = body.get("plan", "professional")
    _stripe = _get_stripe()

    price_id = (
        settings.stripe_starter_price_id if plan == "starter"
        else settings.stripe_pro_price_id
    )
    if not price_id:
        raise HTTPException(400, f"Price ID not configured for plan: {plan}")

    # Get or create Stripe customer
    result = await db.execute(
        __import__('sqlalchemy', fromlist=['select']).select(User).where(User.id == user.user_id)
    )
    db_user = result.scalar_one_or_none()
    customer_id = db_user.stripe_customer_id if db_user else None

    if not customer_id:
        customer = _stripe.Customer.create(email=user.email, metadata={"user_id": user.user_id})
        customer_id = customer.id
        await db.execute(
            sql_update(User).where(User.id == user.user_id).values(stripe_customer_id=customer_id)
        )
        await db.commit()

    origin = str(request.base_url).rstrip("/")
    session = _stripe.checkout.Session.create(
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
    """Handle Stripe webhook events. No JWT auth — uses Stripe signature."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid webhook signature")
    else:
        import json
        event = json.loads(payload)

    event_type = event["type"]
    logger.info(f"Stripe webhook: {event_type}")

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = session.get("metadata", {}).get("user_id")
            plan = session.get("metadata", {}).get("plan", "professional")
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
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
                # Map price_id back to plan
                items = sub.get("items", {}).get("data", [])
                price_id = items[0]["price"]["id"] if items else ""
                price_map = _build_price_map()
                new_plan = price_map.get(price_id, "starter")

            await db.execute(
                sql_update(User).where(User.stripe_customer_id == customer_id).values(plan=new_plan)
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
    """Create a Stripe Customer Portal session."""
    _stripe = _get_stripe()
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()

    if not db_user or not db_user.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer found. Subscribe first.")

    origin = str(request.base_url).rstrip("/")
    session = _stripe.billing_portal.Session.create(
        customer=db_user.stripe_customer_id,
        return_url=f"{origin}/settings",
    )
    return {"url": session.url}


@router.get("/status")
async def billing_status(
    user: CurrentUser = Depends(get_current_user),
):
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
```

**Step 4: Register billing router in main.py**

In `backend/main.py`, add:
```python
from routers.billing import router as billing_router
# ...
app.include_router(billing_router, prefix="/api")
```

Also update `cors_origins` to include `cors_origin_prod`:
```python
origins = list(settings.cors_origins)
if settings.cors_origin_prod:
    origins.append(settings.cors_origin_prod)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # ...
)
```

**Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_billing.py -v
```
Expected: all 2 tests PASS.

**Step 6: Run full suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: no regressions.

**Step 7: Commit**

```bash
cd backend
git add routers/billing.py main.py tests/test_billing.py
git commit -m "feat: Stripe billing router (checkout, webhook, portal, status)"
```

---

## Task 9: Frontend — @supabase/supabase-js + AuthContext

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/contexts/AuthContext.tsx`

**Step 1: Install Supabase client**

```bash
cd frontend && npm install @supabase/supabase-js
```
Expected: package added to node_modules, package.json updated.

**Step 2: Create frontend/src/lib/supabase.ts**

```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase env vars not set — auth will not work')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

**Step 3: Create frontend/src/contexts/AuthContext.tsx**

```typescript
import React, { createContext, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'

interface AuthContextValue {
  session: Session | null
  user: User | null
  loading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  user: null,
  loading: true,
  signOut: async () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Initial session load
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    // Listen for auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
  }

  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
```

**Step 4: Wrap app in AuthProvider in main.tsx**

```typescript
// frontend/src/main.tsx — add AuthProvider
import { AuthProvider } from './contexts/AuthContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

**Step 5: Verify TypeScript compilation**

```bash
cd frontend && npm run build 2>&1 | tail -15
```
Expected: build succeeds (0 errors).

**Step 6: Commit**

```bash
cd frontend
git add package.json package-lock.json src/lib/supabase.ts src/contexts/AuthContext.tsx src/main.tsx
git commit -m "feat: Supabase Auth client + AuthContext + useAuth hook"
```

---

## Task 10: Frontend — auth pages + ProtectedRoute + routing

**Files:**
- Create: `frontend/src/pages/Login.tsx`
- Create: `frontend/src/pages/Register.tsx`
- Create: `frontend/src/pages/ResetPassword.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create frontend/src/components/ProtectedRoute.tsx**

```typescript
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-gray-400">Loading…</div>
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
```

**Step 2: Create frontend/src/pages/Login.tsx**

```typescript
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      navigate('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">HVAC Intelligence</h1>
          <p className="text-gray-400 mt-1">Sign in to your account</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg py-2 text-sm transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <div className="mt-4 text-center text-sm text-gray-500 space-y-2">
          <div>
            <Link to="/reset-password" className="text-blue-400 hover:underline">
              Forgot your password?
            </Link>
          </div>
          <div>
            Don't have an account?{' '}
            <Link to="/register" className="text-blue-400 hover:underline">
              Sign up
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
```

**Step 3: Create frontend/src/pages/Register.tsx**

```typescript
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      setSuccess(true)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
        <div className="w-full max-w-sm text-center">
          <div className="text-green-400 text-lg font-medium mb-2">Check your email</div>
          <p className="text-gray-400 text-sm">
            We sent a confirmation link to <strong className="text-white">{email}</strong>.
            Click it to activate your account.
          </p>
          <Link to="/login" className="mt-6 block text-blue-400 hover:underline text-sm">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">Create account</h1>
          <p className="text-gray-400 mt-1">Start your free Starter plan</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg py-2 text-sm transition-colors"
          >
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="text-blue-400 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
```

**Step 4: Create frontend/src/pages/ResetPassword.tsx**

```typescript
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function ResetPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/update-password`,
    })
    if (error) setError(error.message)
    else setSent(true)
  }

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
        <div className="w-full max-w-sm text-center">
          <div className="text-green-400 text-lg font-medium mb-2">Email sent</div>
          <p className="text-gray-400 text-sm">Check your inbox for a password reset link.</p>
          <Link to="/login" className="mt-6 block text-blue-400 hover:underline text-sm">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">Reset password</h1>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email address</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg py-2 text-sm"
          >
            Send reset link
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          <Link to="/login" className="text-blue-400 hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  )
}
```

**Step 5: Update App.tsx**

```typescript
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DealDesk from './pages/DealDesk'
import Companies from './pages/Companies'
import Settings from './pages/Settings'
import Ops from './pages/Ops'
import Login from './pages/Login'
import Register from './pages/Register'
import ResetPassword from './pages/ResetPassword'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      {/* Public auth routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Protected app routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DealDesk />} />
        <Route path="companies" element={<Companies />} />
        <Route path="ops" element={<Ops />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
```

**Step 6: Verify TypeScript compilation**

```bash
cd frontend && npm run build 2>&1 | tail -15
```
Expected: build succeeds (0 errors).

**Step 7: Commit**

```bash
cd frontend
git add src/pages/Login.tsx src/pages/Register.tsx src/pages/ResetPassword.tsx \
        src/components/ProtectedRoute.tsx src/App.tsx
git commit -m "feat: auth pages (Login/Register/ResetPassword) + ProtectedRoute + routing"
```

---

## Task 11: Frontend — axios interceptor + billing API + Settings billing UI

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Settings.tsx`

**Step 1: Update client.ts with JWT interceptor + billing API**

Add to `frontend/src/api/client.ts`:

```typescript
import { supabase } from '../lib/supabase'

// JWT interceptor — attach token from Supabase session on every request
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Update WebSocket factory to include token
export const createPipelineSocket = (
  onMessage: (data: Record<string, unknown>) => void,
  onClose?: () => void
): WebSocket => {
  supabase.auth.getSession().then(({ data }) => {
    const token = data.session?.access_token ?? ''
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // Use VITE_API_URL for production (Railway backend), fall back to same host for dev
    const apiHost = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host
    const ws = new WebSocket(`${proto}//${apiHost}/api/pipeline/ws?token=${token}`)
    ws.onmessage = e => { try { onMessage(JSON.parse(e.data)) } catch { } }
    ws.onclose = onClose ?? (() => {})
  })
  // Return placeholder — actual ws is created async (fine for current usage pattern)
  // For a cleaner API, callers should use the promise version
}

// Billing API
export const fetchBillingStatus = () =>
  api.get('/billing/status').then(r => r.data)

export const createCheckout = (plan: 'starter' | 'professional') =>
  api.post('/billing/create-checkout', { plan }).then(r => r.data)

export const openBillingPortal = () =>
  api.post('/billing/portal').then(r => r.data)
```

Note: The `createPipelineSocket` function needs a cleaner refactor since it's now async. Replace the existing export with a promise-based version:

```typescript
export const createPipelineSocket = async (
  onMessage: (data: Record<string, unknown>) => void,
  onClose?: () => void
): Promise<WebSocket> => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? ''
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const apiBase = import.meta.env.VITE_API_URL ?? ''
  const wsHost = apiBase
    ? new URL(apiBase.replace(/^http/, 'ws')).host
    : window.location.host
  const ws = new WebSocket(`${proto}//${wsHost}/api/pipeline/ws?token=${token}`)
  ws.onmessage = e => { try { onMessage(JSON.parse(e.data)) } catch { } }
  ws.onclose = onClose ?? (() => {})
  return ws
}
```

Also update the axios `baseURL` to use `VITE_API_URL` if set (for production where frontend and backend are on different domains):

```typescript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api',
  timeout: 30_000,
})
```

**Step 2: Update frontend/src/pages/Ops.tsx to use async socket**

In `Ops.tsx` (or wherever `createPipelineSocket` is called), update the call:

```typescript
// Before:
const ws = createPipelineSocket(handleMessage)

// After:
createPipelineSocket(handleMessage).then(ws => { /* use ws */ })
// or store in a ref for cleanup
```

Find all usages and update accordingly.

**Step 3: Add billing section to Settings.tsx**

In `frontend/src/pages/Settings.tsx`, add a billing card:

```typescript
import { useQuery } from '@tanstack/react-query'
import { fetchBillingStatus, createCheckout, openBillingPortal } from '../api/client'

// Inside Settings component, add:
const { data: billing } = useQuery({
  queryKey: ['billing-status'],
  queryFn: fetchBillingStatus,
})

const handleUpgrade = async (plan: 'starter' | 'professional') => {
  const { url } = await createCheckout(plan)
  window.location.href = url
}

const handleManageBilling = async () => {
  const { url } = await openBillingPortal()
  window.location.href = url
}

// Add this JSX section in the settings page:
{/* Billing Card */}
<div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
  <h2 className="text-lg font-semibold text-white mb-4">Subscription</h2>
  {billing && (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-white font-medium">{billing.planDisplay.name}</div>
          <div className="text-gray-400 text-sm">{billing.planDisplay.price}</div>
        </div>
        <span className="px-3 py-1 bg-blue-600/20 text-blue-400 rounded-full text-xs font-medium uppercase">
          {billing.plan}
        </span>
      </div>
      {billing.scansLimit && (
        <div>
          <div className="flex justify-between text-sm text-gray-400 mb-1">
            <span>Monthly scans</span>
            <span>{billing.scansUsed} / {billing.scansLimit}</span>
          </div>
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all"
              style={{ width: `${Math.min(100, (billing.scansUsed / billing.scansLimit) * 100)}%` }}
            />
          </div>
        </div>
      )}
      <div className="flex gap-3 pt-2">
        {billing.plan === 'starter' && (
          <button
            onClick={() => handleUpgrade('professional')}
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg py-2 transition-colors"
          >
            Upgrade to Professional — $149/mo
          </button>
        )}
        {billing.plan !== 'starter' && (
          <button
            onClick={handleManageBilling}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg py-2 transition-colors"
          >
            Manage Billing
          </button>
        )}
      </div>
    </div>
  )}
</div>
```

**Step 4: Verify TypeScript build**

```bash
cd frontend && npm run build 2>&1 | tail -15
```
Expected: 0 errors.

**Step 5: Commit**

```bash
cd frontend
git add src/api/client.ts src/pages/Settings.tsx src/pages/Ops.tsx
git commit -m "feat: JWT interceptor + billing API + Settings billing card"
```

---

## Task 12: Deployment configs + .env.example

**Files:**
- Create: `frontend/vercel.json`
- Create: `frontend/.env.example`
- Create: `backend/.env.example` (already done in Task 1, verify)
- Modify: `backend/config.py` (CORS_ORIGIN_PROD — already done in Task 1)

**Step 1: Create frontend/vercel.json**

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

**Step 2: Create frontend/.env.example**

```bash
# frontend/.env.example
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://your-backend.railway.app
```

**Step 3: Verify full backend test suite one final time**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```
Expected: all tests pass, no failures.

**Step 4: Verify frontend build**

```bash
cd frontend && npm run build
```
Expected: 0 errors, dist/ folder created.

**Step 5: Commit**

```bash
git add frontend/vercel.json frontend/.env.example backend/.env.example
git commit -m "feat: deployment configs (vercel.json, .env.example files)"
```

---

## First Deploy Checklist (manual steps)

These must be done by the user manually — not automatable by Claude:

1. **Supabase**: Create project → copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL` (PostgreSQL connection string)
2. **Stripe**: Create account → create "Starter" ($49/mo) + "Professional" ($149/mo) products → copy `STRIPE_SECRET_KEY`, Price IDs
3. **Stripe webhook**: Set endpoint to `https://<railway-domain>/api/billing/webhook` → copy `STRIPE_WEBHOOK_SECRET`
4. **Railway**: Deploy backend → set env vars: `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_STARTER_PRICE_ID`, `STRIPE_PRO_PRICE_ID`, `CORS_ORIGIN_PROD`
5. **Run Alembic**: In Railway release command or shell: `alembic upgrade head`
6. **Supabase SQL editor**: Enable RLS policies (copy from design doc Section 3)
7. **Vercel**: Deploy frontend → set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`

---

## Verify Everything Works End-to-End (local smoke test)

After all tasks:

```bash
# Backend
cd backend && python -m pytest tests/ -v
# Expected: all tests pass

# Frontend
cd frontend && npm run build
# Expected: 0 TypeScript errors, dist/ created

# Start backend locally
cd backend && uvicorn main:app --reload --port 8000
# Then: curl http://localhost:8000/api/health → {"status":"ok",...}
# Then: curl http://localhost:8000/api/companies → {"detail":"Missing Authorization header"}
# Expected: health returns 200, companies returns 401
```
