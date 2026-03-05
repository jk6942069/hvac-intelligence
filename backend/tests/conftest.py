"""Shared pytest fixtures for backend tests."""
import pytest
import sys
import os

# Make backend modules importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Required for anyio-based async tests
pytest_plugins = ('anyio',)
