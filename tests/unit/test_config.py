from __future__ import annotations

from dmb_mcp.config_loader import load_leagues
from dmb_mcp.settings import Settings, package_root


def test_load_leagues_from_example_config() -> None:
    settings = Settings(
        db_path=package_root() / "data" / "is_scout.db",
        session_path=package_root() / ".is_session",
        config_path=package_root() / "config" / "leagues.example.json",
        entry_team_id=None,
    )
    leagues = load_leagues(settings)
    assert len(leagues) == 1
    assert leagues[0].entry_team_id == "YOUR_ENTRY_TEAM_ID"
    assert leagues[0].active is True


def test_load_leagues_from_env(example_settings: Settings) -> None:
    leagues = load_leagues(example_settings)
    assert leagues[0].display == "Example League"
