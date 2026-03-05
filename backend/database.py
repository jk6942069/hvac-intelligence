from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

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
    Idempotent column migrations for SQLite.
    SQLAlchemy create_all won't add columns to existing tables,
    so we run ALTER TABLE ADD COLUMN statements and swallow
    'duplicate column' errors safely.
    """
    from sqlalchemy import text

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
    ]

    async with engine.connect() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                await conn.commit()
            except Exception:
                # Column already exists — safe to ignore
                pass
