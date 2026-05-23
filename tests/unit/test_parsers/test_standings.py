from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from dmb_mcp.scraper.parsers import parse_standings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "html"


@pytest.fixture
def standings_html() -> str:
    return (FIXTURES / "standings.html").read_text()


def test_parse_standings_returns_rows(standings_html: str) -> None:
    soup = BeautifulSoup(standings_html, "lxml")
    rows = parse_standings(soup, "test_league")
    assert len(rows) == 2
    assert rows[0]["w"] == 10
    assert rows[0]["l"] == 5
    assert rows[1]["rs"] == 40
