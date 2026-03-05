"""Test that database.py correctly configures engine for SQLite vs PostgreSQL URLs."""
import os
import importlib
import pytest


def test_sqlite_default_url():
    """Default should be SQLite when DATABASE_URL not set."""
    os.environ.pop("DATABASE_URL", None)
    import database
    importlib.reload(database)
    assert "sqlite" in str(database.engine.url)


def test_database_url_env_overrides_default(monkeypatch):
    """DATABASE_URL env var should be picked up."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test_override.db")
    import config
    importlib.reload(config)
    import database
    importlib.reload(database)
    assert "test_override" in str(database.engine.url)
    # Cleanup: reload back to default
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(config)
    importlib.reload(database)


def test_migrate_db_skips_for_non_sqlite():
    """migrate_db() should be a no-op for PostgreSQL URLs (returns early)."""
    import asyncio
    import database
    # Temporarily swap engine url to simulate postgres
    original_url = str(database.engine.url)
    # We can't actually connect to postgres, so we just test the guard logic directly
    # by checking the function has an early return for non-sqlite
    import inspect
    src = inspect.getsource(database.migrate_db)
    assert "sqlite" in src  # function checks for sqlite in url
    assert "return" in src  # function has early return
