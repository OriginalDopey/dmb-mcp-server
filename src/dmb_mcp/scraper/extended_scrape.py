"""Extended scrape orchestration for leaderboards, injuries, reference pages."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from dmb_mcp.db.database import Database
from dmb_mcp.db.extended import replace_league_rows, replace_team_rows
from dmb_mcp.scraper.league_scraper import ScrapeMode
from dmb_mcp.scraper.parsers.extended import (
    FIELDING_POSITIONS,
    parse_batting_splits,
    parse_fielding_leaders,
    parse_injuries,
    parse_leaderboards,
    parse_league_transactions,
    parse_pitching_splits,
    parse_team_vs_team,
    parse_trade_view,
)
from dmb_mcp.scraper.session import ISSession
from dmb_mcp.settings import Settings, package_root


class ExtendedScraper:
    """Scrape pages not covered by the legacy league scraper body."""

    def __init__(
        self,
        db: Database,
        session: ISSession,
        settings: Settings | None = None,
    ):
        self.db = db
        self.session = session
        self.settings = settings or Settings.from_env()

    def _url(self, path: str, **params: str) -> str:
        from urllib.parse import urlencode

        qs = urlencode(params)
        return f"{self.settings.base_url}{path}?{qs}" if qs else f"{self.settings.base_url}{path}"

    def run(
        self,
        entry_team_id: str,
        league_id: str,
        teams: list[dict[str, str]],
        *,
        mode: ScrapeMode,
        verbose: bool = False,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        def log(msg: str) -> None:
            if verbose:
                print(msg)

        total = 0
        errors: list[str] = []

        if mode in ("refresh", "full"):
            total += self._scrape_injuries(entry_team_id, league_id, teams, log)
            total += self._scrape_league_transactions(entry_team_id, league_id, log)
            if progress:
                progress(0.4, "Injuries and league transactions refreshed")

        if mode == "full":
            total += self._scrape_leaderboards(entry_team_id, league_id, log, errors)
            total += self._scrape_fielding_leaders(entry_team_id, league_id, log, errors)
            total += self._scrape_team_vs_team(entry_team_id, league_id, log, errors)
            total += self._scrape_trade_view(entry_team_id, league_id, log, errors)
            total += self._scrape_splits(entry_team_id, league_id, teams, log)
            if progress:
                progress(0.8, "Extended full scrape pages complete")

        self.db.commit()
        return {"records": total, "errors": errors}

    def _scrape_leaderboards(
        self, entry_team_id: str, league_id: str, log: Callable[[str], None], errors: list[str]
    ) -> int:
        total = 0
        for board_type in ("Batting", "Pitching"):
            url = self._url(
                "/bball/league/leaderboards",
                type=board_type,
                curTeam=entry_team_id,
            )
            soup, err = self.session.get_soup(url)
            if err:
                errors.append(f"leaderboards/{board_type}: {err}")
                continue
            rows = parse_leaderboards(soup, league_id, board_type.lower())
            total += replace_league_rows(self.db, "league_leaderboards", league_id, rows)
            log(f"    leaderboards/{board_type}: {len(rows)} rows")
        return total

    def _scrape_fielding_leaders(
        self, entry_team_id: str, league_id: str, log: Callable[[str], None], errors: list[str]
    ) -> int:
        total = 0
        all_rows: list[dict[str, Any]] = []
        for pos_code, pos_name in FIELDING_POSITIONS.items():
            url = self._url(
                "/bball/league/complete_leaders",
                sort="FA",
                xtra="",
                stat_type="Fielding",
                pos=pos_code,
                post_gametype="0",
                curTeam=entry_team_id,
                expandit="",
                num_games="0",
            )
            soup, err = self.session.get_soup(url)
            if err:
                errors.append(f"fielding/{pos_name}: {err}")
                continue
            all_rows.extend(parse_fielding_leaders(soup, league_id, pos_name))
        total += replace_league_rows(self.db, "fielding_leaders", league_id, all_rows)
        log(f"    fielding leaders: {len(all_rows)} rows")
        return total

    def _scrape_team_vs_team(
        self, entry_team_id: str, league_id: str, log: Callable[[str], None], errors: list[str]
    ) -> int:
        url = self._url("/bball/league/team_vs_team", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            errors.append(f"team_vs_team: {err}")
            return 0
        rows = parse_team_vs_team(soup, league_id)
        n = replace_league_rows(self.db, "team_vs_team", league_id, rows)
        log(f"    team vs team: {n} rows")
        return n

    def _scrape_league_transactions(
        self, entry_team_id: str, league_id: str, log: Callable[[str], None]
    ) -> int:
        url = self._url("/bball/league/transactions", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            log(f"    league transactions: {err}")
            return 0
        rows = parse_league_transactions(soup, league_id)
        n = replace_league_rows(self.db, "league_transactions", league_id, rows)
        log(f"    league transactions: {n} rows")
        return n

    def _scrape_trade_view(
        self, entry_team_id: str, league_id: str, log: Callable[[str], None], errors: list[str]
    ) -> int:
        url = self._url("/bball/frontoffice/trade_view", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            errors.append(f"trade_view: {err}")
            log("    trade_view: not accessible (auth required for some leagues)")
            return 0
        rows = parse_trade_view(soup, league_id)
        n = replace_league_rows(self.db, "trade_view", league_id, rows)
        log(f"    trade_view: {n} rows")
        return n

    def _scrape_injuries(
        self,
        entry_team_id: str,
        league_id: str,
        teams: list[dict[str, str]],
        log: Callable[[str], None],
    ) -> int:
        total = 0
        for team in teams:
            tid = team["team_id"]
            url = self._url("/bball/team/injuries", curTeam=entry_team_id, teamID=tid)
            soup, err = self.session.get_soup(url)
            if err:
                continue
            rows = parse_injuries(soup, tid, league_id)
            total += replace_team_rows(self.db, "injuries", tid, rows)
        log(f"    injuries: {total} rows across {len(teams)} teams")
        return total

    def _scrape_splits(
        self,
        entry_team_id: str,
        league_id: str,
        teams: list[dict[str, str]],
        log: Callable[[str], None],
    ) -> int:
        total = 0
        split_map = {
            "batting_splits": (
                "/bball/team/batting",
                parse_batting_splits,
                ("vs_LHP", "vs_RHP"),
            ),
            "pitching_splits": (
                "/bball/team/pitching",
                parse_pitching_splits,
                ("vs_LHB", "vs_RHB"),
            ),
        }
        for table, (path, parser, splits) in split_map.items():
            for team in teams:
                tid = team["team_id"]
                all_rows: list[dict[str, Any]] = []
                for split_type in splits:
                    url = self._url(
                        path,
                        curTeam=entry_team_id,
                        teamID=tid,
                        split_type=split_type,
                    )
                    soup, err = self.session.get_soup(url)
                    if err:
                        continue
                    all_rows.extend(parser(soup, tid, league_id, split_type))
                total += replace_team_rows(self.db, table, tid, all_rows)
        log(f"    splits: {total} rows")
        return total


def load_static_record_boards() -> dict[str, Any]:
    path = package_root() / "config" / "record_boards_2026_standard.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"source": "static", "batting": {}, "pitching": {}}
