"""Shared pytest fixtures and env defaults for portable CI/local runs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _default_test_env() -> None:
    """Use example config and repo-local paths unless the test overrides them."""
    os.environ.setdefault("DMB_CONFIG_PATH", str(REPO_ROOT / "config" / "leagues.example.json"))
    os.environ.setdefault("DMB_DB_PATH", str(REPO_ROOT / "data" / "test_is_scout.db"))
    os.environ.setdefault("DMB_SESSION_PATH", str(REPO_ROOT / ".is_session"))


@pytest.fixture
def example_settings():
    from dmb_mcp.settings import Settings

    return Settings(
        db_path=REPO_ROOT / "data" / "test_is_scout.db",
        session_path=REPO_ROOT / ".is_session",
        config_path=REPO_ROOT / "config" / "leagues.example.json",
        entry_team_id=None,
    )
