"""HTML parsers for ImagineSports pages."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from dmb_mcp.settings import Settings, get_settings


def _load_parsers(settings: Settings | None = None) -> dict[str, Any]:
    s = settings or get_settings()
    body_path = Path(__file__).with_name("_parsers_body.py")
    namespace: dict[str, Any] = {
        "re": re,
        "datetime": datetime,
        "timezone": timezone,
        "BeautifulSoup": BeautifulSoup,
        "urlparse": urlparse,
        "parse_qs": parse_qs,
        "BASE_URL": s.base_url,
    }
    exec(body_path.read_text(), namespace)
    return namespace


def get_parser(name: str, settings: Settings | None = None):
    return _load_parsers(settings)[name]


def parse_standings(soup, league_id, settings: Settings | None = None):
    return get_parser("parse_standings", settings)(soup, league_id)


def parse_roster(soup, team_id, league_id, settings: Settings | None = None):
    return get_parser("parse_roster", settings)(soup, team_id, league_id)


def parse_teams_from_league_page(soup, settings: Settings | None = None):
    return get_parser("parse_teams_from_league_page", settings)(soup)


def parse_league_rules(soup, league_id, settings: Settings | None = None):
    return get_parser("parse_league_rules", settings)(soup, league_id)


def parse_psimstats_popup(soup, settings: Settings | None = None):
    return get_parser("parse_psimstats_popup", settings)(soup)


__all__ = [
    "_load_parsers",
    "get_parser",
    "parse_league_rules",
    "parse_psimstats_popup",
    "parse_roster",
    "parse_standings",
    "parse_teams_from_league_page",
]
