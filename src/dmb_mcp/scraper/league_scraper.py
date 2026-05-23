"""League scraping orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse

from dmb_mcp.db.database import Database
from dmb_mcp.scraper.parsers import _load_parsers
from dmb_mcp.scraper.session import ISSession
from dmb_mcp.settings import Settings

ScrapeMode = Literal["full", "refresh", "tracker"]


def _load_league_scraper_class(settings: Settings) -> type:
    parsers = _load_parsers(settings)
    body_path = Path(__file__).with_name("_league_scraper_body.py")
    namespace: dict[str, Any] = {
        "time": time,
        "urlencode": urlencode,
        "urlparse": urlparse,
        "parse_qs": parse_qs,
        "BASE_URL": settings.base_url,
        "Database": Database,
        "ISSession": ISSession,
        **parsers,
    }
    exec(body_path.read_text(), namespace)
    return namespace["LeagueScraper"]


class LeagueScraper:
    """Scrape all data for one ImagineSports league."""

    def __init__(self, db: Database, session: ISSession, settings: Settings | None = None):
        self.db = db
        self.session = session
        self.settings = settings or Settings.from_env()
        scraper_cls = _load_league_scraper_class(self.settings)
        self._inner = scraper_cls(db=db, session=session._inner)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def run(
        self,
        entry_team_id: str,
        mode: ScrapeMode = "refresh",
        *,
        verbose: bool = False,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        start = time.time()
        if progress:
            progress(0.0, f"Starting {mode} scrape for {entry_team_id[:12]}…")

        if mode == "full":
            ok = self._inner.scrape_league(entry_team_id, verbose=verbose)
        elif mode == "tracker":
            ok = self._inner.refresh_league_tracker_only(entry_team_id, verbose=verbose)
        else:
            ok = self._inner.refresh_league(entry_team_id, verbose=verbose)

        duration = round(time.time() - start, 1)
        league_row = self.db.execute(
            """
            SELECT league_id, name FROM leagues
            WHERE entry_team_id = ?
            ORDER BY last_scraped DESC LIMIT 1
            """,
            [entry_team_id],
        ).fetchone()
        league_id = league_row["league_id"] if league_row else None

        if ok and league_id:
            teams_rows = self.db.execute(
                "SELECT team_id, name FROM teams WHERE league_id = ? ORDER BY name",
                [league_id],
            ).fetchall()
            teams = [{"team_id": r["team_id"], "name": r["name"]} for r in teams_rows]
            if teams:
                from dmb_mcp.scraper.extended_scrape import ExtendedScraper

                ext = ExtendedScraper(self.db, self.session, self.settings)
                ext.run(
                    entry_team_id,
                    league_id,
                    teams,
                    mode=mode,
                    verbose=verbose,
                    progress=progress,
                )

        if progress:
            progress(1.0, "Scrape complete")

        return {
            "ok": bool(ok),
            "entry_team_id": entry_team_id,
            "mode": mode,
            "league_id": league_id,
            "league_name": league_row["name"] if league_row else None,
            "duration_s": duration,
        }
