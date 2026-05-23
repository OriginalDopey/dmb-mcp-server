"""Application context and team/league scoping."""

from __future__ import annotations

from dataclasses import dataclass

from dmb_mcp.config_loader import load_leagues
from dmb_mcp.db.database import Database
from dmb_mcp.scraper.league_scraper import LeagueScraper
from dmb_mcp.scraper.session import ISSession
from dmb_mcp.settings import Settings


@dataclass
class AppContext:
    settings: Settings
    db: Database
    session: ISSession
    scraper: LeagueScraper

    @classmethod
    def create(cls, settings: Settings | None = None) -> AppContext:
        s = settings or Settings.from_env()
        db = Database(settings=s)
        session = ISSession(settings=s)
        scraper = LeagueScraper(db=db, session=session, settings=s)
        return cls(settings=s, db=db, session=session, scraper=scraper)

    def close(self) -> None:
        self.db.close()

    def resolve_entry_team_id(self, entry_team_id: str | None = None) -> str:
        if entry_team_id and entry_team_id != "mine":
            return entry_team_id
        if self.settings.entry_team_id:
            return self.settings.entry_team_id
        leagues = load_leagues(self.settings)
        if leagues:
            return leagues[0].entry_team_id
        raise ValueError(
            "No entry_team_id configured. Set DMB_ENTRY_TEAM_ID or config/leagues.json"
        )

    def resolve_league_id(self, league_id: str | None = None) -> str:
        if league_id and league_id not in ("mine", ""):
            return league_id
        entry = self.resolve_entry_team_id("mine")
        row = self.db.execute(
            """
            SELECT league_id FROM leagues
            WHERE entry_team_id = ?
            ORDER BY last_scraped DESC LIMIT 1
            """,
            [entry],
        ).fetchone()
        if row:
            return str(row["league_id"])
        raise ValueError(f"No league found for entry team {entry}")

    def resolve_team_id(self, team_id: str | None = None) -> str:
        if team_id and team_id not in ("mine", ""):
            return team_id
        entry = self.resolve_entry_team_id("mine")
        row = self.db.execute(
            "SELECT owner_team_id, league_id FROM leagues WHERE entry_team_id = ? LIMIT 1",
            [entry],
        ).fetchone()
        if row and row["owner_team_id"]:
            return str(row["owner_team_id"])
        team_row = self.db.execute(
            """
            SELECT t.team_id FROM teams t
            JOIN leagues l ON l.league_id = t.league_id
            WHERE l.entry_team_id = ?
            LIMIT 1
            """,
            [entry],
        ).fetchone()
        if team_row:
            return str(team_row["team_id"])
        return entry
