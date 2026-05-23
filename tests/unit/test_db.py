"""Repository tests against an in-memory SQLite database."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dmb_mcp.db.database import Database
from dmb_mcp.db.repository import Repository


@pytest.fixture
def repo() -> Repository:
    db = Database(db_path=":memory:")
    now = datetime.now(UTC).isoformat()
    league_id = "TEST_LEAGUE"
    team_id = "TEAM_A"

    db.upsert_league(league_id, name="Test League", num_teams=1)
    db.upsert_team(team_id, league_id, name="Test Team")
    db.execute(
        """
        INSERT INTO standings
            (team_id, league_id, scraped_at, division, w, l, pct, gb, rs, ra, streak, l10)
        VALUES (?, ?, ?, 'East', 10, 5, 0.667, '-', 55, 40, 'W3', '7-3')
        """,
        [team_id, league_id, now],
    )
    db.upsert_league_rules(league_id, {"dh": "Yes", "era": "Standard"})
    db.execute(
        """
        INSERT INTO league_leaderboards
            (league_id, board_type, category, rank, player, team_abbr, value, scraped_at)
        VALUES (?, 'batting', 'Home Runs', 1, 'Ruth, Babe', 'NYY', '60', ?)
        """,
        [league_id, now],
    )
    db.commit()
    yield Repository(db)
    db.close()


def test_standings(repo: Repository) -> None:
    rows = repo.standings("TEST_LEAGUE")
    assert len(rows) == 1
    assert rows[0].team_name == "Test Team"
    assert rows[0].wins == 10
    assert rows[0].losses == 5


def test_league_rules(repo: Repository) -> None:
    rules = repo.league_rules("TEST_LEAGUE")
    assert rules["dh"] == "Yes"
    assert rules["era"] == "Standard"


def test_leaderboards(repo: Repository) -> None:
    rows = repo.leaderboards("TEST_LEAGUE", board_type="batting")
    assert len(rows) == 1
    assert rows[0]["player"] == "Ruth, Babe"
    assert rows[0]["value"] == "60"
