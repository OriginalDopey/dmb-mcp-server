"""Tests for extended HTML parsers."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from dmb_mcp.scraper.parsers.extended import (
    parse_fielding_leaders,
    parse_injuries,
    parse_leaderboards,
    parse_league_transactions,
    parse_park_reference,
    parse_team_vs_team,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


@pytest.fixture
def league_id() -> str:
    return "TEST_LEAGUE"


def _load(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "lxml")


def test_parse_leaderboards(league_id: str) -> None:
    rows = parse_leaderboards(_load("leaderboards_batting.html"), league_id, "batting")
    assert len(rows) >= 50
    assert rows[0]["category"] == "Home Runs"
    assert rows[0]["player"] == "Vaughn, Greg"
    assert rows[0]["team_abbr"] == "CRL"
    assert rows[0]["value"] == "7"


def test_parse_fielding_leaders(league_id: str) -> None:
    rows = parse_fielding_leaders(_load("fielding_leaders_p.html"), league_id, "P")
    assert len(rows) >= 40
    assert rows[0]["player"] == "Gibson, Bob"
    assert rows[0]["position"] == "P"


def test_parse_team_vs_team(league_id: str) -> None:
    rows = parse_team_vs_team(_load("team_vs_team.html"), league_id)
    assert len(rows) > 50
    assert any(r["record"] == "2-3" for r in rows)


def test_parse_league_transactions(league_id: str) -> None:
    rows = parse_league_transactions(_load("league_transactions.html"), league_id)
    assert len(rows) >= 100
    assert "activated" in rows[0]["tx_text"].lower()


def test_parse_injuries_empty(league_id: str) -> None:
    rows = parse_injuries(_load("injuries.html"), "TEAM1", league_id)
    assert rows == []


def test_parse_park_reference() -> None:
    rows = parse_park_reference(_load("park_reference.html"))
    assert len(rows) >= 50
    assert any("Yankee" in r["park_name"] for r in rows)
