"""Repository query coverage for newly exposed MCP query types."""

from __future__ import annotations

import sqlite3

from dmb_mcp.db.database import Database
from dmb_mcp.db.repository import Repository


def test_team_ratings_and_trade_view(tmp_path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE batter_ratings (id INTEGER PRIMARY KEY, team_id TEXT, player TEXT);
        CREATE TABLE pitcher_ratings (id INTEGER PRIMARY KEY, team_id TEXT, player TEXT);
        CREATE TABLE fielder_ratings (id INTEGER PRIMARY KEY, team_id TEXT, player TEXT);
        CREATE TABLE fielding_stats (id INTEGER PRIMARY KEY, team_id TEXT, player TEXT);
        CREATE TABLE trade_view (
            id INTEGER PRIMARY KEY, league_id TEXT, status TEXT,
            proposing_team TEXT, detail_text TEXT, scraped_at TEXT
        );
        INSERT INTO batter_ratings (team_id, player) VALUES ('T1', 'Ruth');
        INSERT INTO trade_view (league_id, status, proposing_team, detail_text, scraped_at)
            VALUES ('L1', 'pending', 'Team A', 'offer', 'now');
        """
    )
    conn.commit()
    conn.close()

    repo = Repository(Database(db_path))
    ratings = repo.team_ratings("T1")
    assert ratings["batters"][0]["player"] == "Ruth"
    assert repo.team_fielding_stats("T1") == []
    trades = repo.trade_view("L1")
    assert trades[0]["proposing_team"] == "Team A"
