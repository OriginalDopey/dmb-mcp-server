"""Reference data fetchers (parks, record boards)."""

from __future__ import annotations

import json
from typing import Any

from dmb_mcp.db.database import Database
from dmb_mcp.db.extended import (
    get_reference_cache,
    park_reference_count,
    replace_record_boards,
    set_reference_cache,
    upsert_park_reference,
)
from dmb_mcp.scraper.extended_scrape import load_static_record_boards
from dmb_mcp.scraper.parsers.extended import parse_park_reference, parse_record_boards
from dmb_mcp.scraper.session import ISSession
from dmb_mcp.settings import Settings

RECORD_BOARD_URLS = {
    "2026_standard_batting": (
        "/bball/leaders/boards/teams_players_summary"
        "?stat_type=Batting&sort=BA&source=player&year=2026"
        "&leagues=standard&catalog=Career"
    ),
    "2026_standard_pitching": (
        "/bball/leaders/boards/teams_players_summary"
        "?stat_type=pitching&sort=ERA&source=player&year=2026"
        "&leagues=standard&catalog=Career"
    ),
}


class ReferenceService:
    def __init__(
        self,
        db: Database,
        session: ISSession,
        settings: Settings | None = None,
    ):
        self.db = db
        self.session = session
        self.settings = settings or Settings.from_env()

    def parks(self, *, force: bool = False) -> dict[str, Any]:
        cache_key = "parks_reference"
        if not force:
            cached = get_reference_cache(self.db, cache_key)
            if cached:
                return cached
            if park_reference_count(self.db) > 0:
                rows = self.db.execute(
                    """
                    SELECT park_name, years, city, surface, cover
                    FROM park_reference
                    ORDER BY park_name
                    """
                ).fetchall()
                payload = {
                    "source": "database",
                    "count": len(rows),
                    "parks": [dict(r) for r in rows],
                }
                set_reference_cache(self.db, cache_key, payload, ttl_days=365)
                self.db.commit()
                return payload

        url = f"{self.settings.base_url}/bball/reference/parks/popup"
        soup, err = self.session.get_soup(url)
        if err:
            return {"ok": False, "error": err, "source": "fetch_failed"}

        rows = parse_park_reference(soup)
        count = upsert_park_reference(self.db, rows)
        payload = {
            "ok": True,
            "source": "live",
            "count": count,
            "parks": [
                {
                    "park_name": r["park_name"],
                    "years": r.get("years", ""),
                    "city": r.get("city", ""),
                }
                for r in rows[:20]
            ],
            "truncated_preview": count > 20,
        }
        set_reference_cache(self.db, cache_key, payload, ttl_days=365)
        self.db.commit()
        return payload

    def record_boards(self, *, force: bool = False) -> dict[str, Any]:
        cache_key = "record_boards_2026_standard"
        if not force:
            cached = get_reference_cache(self.db, cache_key)
            if cached:
                return cached

        live: dict[str, Any] = {"boards": {}, "errors": []}
        for board_key, path in RECORD_BOARD_URLS.items():
            url = f"{self.settings.base_url}{path}"
            soup, err = self.session.get_soup(url)
            if err:
                live["errors"].append(f"{board_key}: {err}")
                continue
            rows = parse_record_boards(soup, board_key)
            replace_record_boards(self.db, board_key, rows)
            live["boards"][board_key] = len(rows)

        if live["boards"]:
            payload = {
                "ok": True,
                "source": "live",
                "boards": live["boards"],
                "errors": live["errors"],
            }
            set_reference_cache(self.db, cache_key, payload, ttl_days=7)
            self.db.commit()
            return payload

        static = load_static_record_boards()
        payload = {
            "ok": True,
            "source": "static_fallback",
            "note": (
                "Live IS record boards require authenticated session; using bundled thresholds."
            ),
            "data": static,
            "errors": live["errors"],
        }
        set_reference_cache(self.db, cache_key, payload, ttl_days=7)
        self.db.commit()
        return payload

    def fetch(self, ref_type: str, *, force: bool = False) -> str:
        if ref_type == "parks":
            return json.dumps(self.parks(force=force), indent=2)
        if ref_type == "record_boards":
            return json.dumps(self.record_boards(force=force), indent=2)
        raise ValueError(f"Unknown reference type: {ref_type}")
