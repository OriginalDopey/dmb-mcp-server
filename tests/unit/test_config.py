from __future__ import annotations

from dmb_mcp.config_loader import load_leagues
from dmb_mcp.settings import Settings


def test_load_leagues_from_config() -> None:
    settings = Settings.from_env()
    leagues = load_leagues(settings)
    assert len(leagues) >= 1
    assert leagues[0].entry_team_id
