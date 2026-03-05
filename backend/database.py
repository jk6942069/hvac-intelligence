import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

logger = logging.getLogger(__name__)


def _make_engine():
    url = os.getenv("DATABASE_URL", settings.database_url)
    is_sqlite = url.startswith("sqlite")
    kwargs = {"echo": settings.debug}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # asyncpg pool sizing for Railway free tier (5 connections)
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_async_engine(url, **kwargs)


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
    In production (PostgreSQL), Alembic manages all schema changes.
    """
    from sqlalchemy import text
    url = str(engine.url)
    if "sqlite" not in url:
        logger.info("Skipping migrate_db() — using PostgreSQL (Alembic manages schema)")
        return

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
        # SaaS multi-tenancy columns (v4)
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
            logger.warning(f"Workflow migration: {e}")
