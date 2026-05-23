"""FastMCP server entry point."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP

from dmb_mcp.config_loader import active_leagues, load_leagues
from dmb_mcp.context import AppContext
from dmb_mcp.db.repository import Repository
from dmb_mcp.models import AuthResult, ScrapeResult
from dmb_mcp.reference import ReferenceService
from dmb_mcp.scraper.league_scraper import ScrapeMode


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    ctx = AppContext.create()
    try:
        yield ctx
    finally:
        ctx.close()


mcp = FastMCP("dmb", lifespan=app_lifespan, json_response=True)


def _ctx_app(ctx: Context) -> AppContext:
    return ctx.request_context.lifespan_context


@mcp.tool()
async def auth(
    action: Literal["set_cookie", "status"],
    cookie: str | None = None,
    ctx: Context | None = None,
) -> AuthResult:
    """Set or validate the ImagineSports session cookie."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    if action == "set_cookie":
        if not cookie:
            return AuthResult(valid=False, message="cookie is required for set_cookie")
        app.session.save_cookie(cookie)
        return AuthResult(valid=True, message=f"Cookie saved to {app.settings.session_path}")
    status = app.session.auth_status()
    return AuthResult(valid=bool(status["valid"]), message=str(status["message"]))


@mcp.tool()
async def scrape(
    entry_team_id: str | None = None,
    mode: ScrapeMode = "refresh",
    ctx: Context | None = None,
) -> ScrapeResult:
    """Scrape one league. Modes: full, refresh (incremental), tracker (standings only)."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    target = app.resolve_entry_team_id(entry_team_id)

    async def progress(pct: float, message: str) -> None:
        if ctx is not None:
            await ctx.report_progress(progress=pct, total=1.0, message=message)

    def sync_progress(pct: float, message: str) -> None:
        pass

    result = app.scraper.run(target, mode=mode, verbose=False, progress=sync_progress)
    await progress(1.0, "done")
    return ScrapeResult(
        ok=result["ok"],
        entry_team_id=target,
        mode=mode,
        league_id=result.get("league_id"),
        league_name=result.get("league_name"),
        duration_s=result.get("duration_s", 0.0),
        message="Scrape finished" if result["ok"] else "Scrape failed",
    )


@mcp.tool()
async def scrape_all(
    mode: ScrapeMode = "refresh",
    ctx: Context | None = None,
) -> list[ScrapeResult]:
    """Scrape all active leagues from config/leagues.json."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    results: list[ScrapeResult] = []
    leagues = active_leagues(app.settings)
    for i, league in enumerate(leagues):
        if ctx is not None:
            await ctx.report_progress(
                progress=(i + 1) / max(len(leagues), 1),
                total=1.0,
                message=f"Scraping {league.display}",
            )
        one = await scrape(entry_team_id=league.entry_team_id, mode=mode, ctx=ctx)
        results.append(one)
    return results


@mcp.tool()
async def query(
    type: str,
    target_id: str = "mine",
    options: dict | None = None,
    ctx: Context | None = None,
) -> str:
    """Query cached DB data. Types: standings, roster, financials, rules, transactions, player."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    repo = Repository(app.db)
    opts = options or {}

    if type == "standings":
        league_id = app.resolve_league_id(target_id)
        rows = repo.standings(league_id)
        return json.dumps([r.model_dump() for r in rows], indent=2)
    if type == "roster":
        team_id = app.resolve_team_id(target_id)
        rows = repo.roster(team_id)
        return json.dumps([r.model_dump() for r in rows], indent=2)
    if type == "financials":
        team_id = app.resolve_team_id(target_id)
        fin = repo.financials(team_id)
        return json.dumps(fin.model_dump() if fin else {}, indent=2)
    if type == "rules":
        league_id = app.resolve_league_id(target_id)
        return json.dumps(repo.league_rules(league_id), indent=2)
    if type == "transactions":
        league_id = app.resolve_league_id(target_id)
        limit = int(opts.get("limit", 50))
        return json.dumps(repo.transactions(league_id, limit=limit), indent=2)
    if type == "player":
        name = opts.get("name", target_id if target_id != "mine" else "")
        if not name:
            raise ValueError("player query requires options.name or a player target_id")
        row = repo.player_psimstats(name)
        return json.dumps(row or {}, indent=2)
    if type == "leaderboards":
        league_id = app.resolve_league_id(target_id)
        board_type = str(opts.get("board_type", "batting"))
        return json.dumps(repo.leaderboards(league_id, board_type=board_type), indent=2)
    if type == "fielding_leaders":
        league_id = app.resolve_league_id(target_id)
        position = opts.get("position")
        return json.dumps(
            repo.fielding_leaders(league_id, position=str(position) if position else None),
            indent=2,
        )
    if type == "team_vs_team":
        league_id = app.resolve_league_id(target_id)
        return json.dumps(repo.team_vs_team(league_id), indent=2)
    if type == "league_transactions":
        league_id = app.resolve_league_id(target_id)
        limit = int(opts.get("limit", 100))
        return json.dumps(repo.league_transactions(league_id, limit=limit), indent=2)
    if type == "injuries":
        team_id = app.resolve_team_id(target_id)
        return json.dumps(repo.injuries(team_id), indent=2)
    if type == "splits":
        team_id = app.resolve_team_id(target_id)
        stat_type = str(opts.get("stat_type", "batting"))
        split_type = opts.get("split_type")
        split_arg = str(split_type) if split_type else None
        if stat_type == "pitching":
            rows = repo.pitching_splits(team_id, split_type=split_arg)
        else:
            rows = repo.batting_splits(team_id, split_type=split_arg)
        return json.dumps(rows, indent=2)
    raise ValueError(f"Unknown query type: {type}")


@mcp.tool()
async def report(type: str, target_id: str = "mine", ctx: Context | None = None) -> str:
    """Generate a readable report. Types: league_summary, team_snapshot."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    repo = Repository(app.db)
    if type == "league_summary":
        league_id = app.resolve_league_id(target_id)
        return repo.league_summary_text(league_id)
    if type == "team_snapshot":
        team_id = app.resolve_team_id(target_id)
        roster = repo.roster(team_id)
        fin = repo.financials(team_id)
        lines = [f"Team {team_id}", f"Roster ({len(roster)} players):"]
        for p in roster[:28]:
            lines.append(f"  {p.player} ({p.position}) {p.salary}")
        if fin:
            lines.append(
                f"Finance: cash {fin.balance}, "
                f"roster ${fin.roster_salary_num or 0:,}, park {fin.park}"
            )
        return "\n".join(lines)
    raise ValueError(f"Unknown report type: {type}")


@mcp.tool()
async def reference(
    type: Literal["parks", "record_boards"],
    force: bool = False,
    ctx: Context | None = None,
) -> str:
    """Fetch reference data. Parks cache until force=true. Record boards refresh weekly max."""
    app = _ctx_app(ctx)  # type: ignore[arg-type]
    svc = ReferenceService(app.db, app.session, app.settings)
    return svc.fetch(type, force=force)


@mcp.resource("standings://{league_id}")
def standings_resource(league_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_league_id(league_id)
    rows = repo.standings(resolved)
    return json.dumps([r.model_dump() for r in rows], indent=2)


@mcp.resource("roster://{team_id}")
def roster_resource(team_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_team_id(team_id)
    rows = repo.roster(resolved)
    return json.dumps([r.model_dump() for r in rows], indent=2)


@mcp.resource("financials://{team_id}")
def financials_resource(team_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_team_id(team_id)
    fin = repo.financials(resolved)
    return json.dumps(fin.model_dump() if fin else {}, indent=2)


@mcp.resource("rules://{league_id}")
def rules_resource(league_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_league_id(league_id)
    return json.dumps(repo.league_rules(resolved), indent=2)


@mcp.resource("transactions://{league_id}")
def transactions_resource(league_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_league_id(league_id)
    return json.dumps(repo.transactions(resolved), indent=2)


@mcp.resource("leaderboards://{league_id}/{board_type}")
def leaderboards_resource(league_id: str, board_type: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_league_id(league_id)
    return json.dumps(repo.leaderboards(resolved, board_type=board_type), indent=2)


@mcp.resource("injuries://{team_id}")
def injuries_resource(team_id: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_team_id(team_id)
    return json.dumps(repo.injuries(resolved), indent=2)


@mcp.resource("splits://{team_id}/{stat_type}")
def splits_resource(team_id: str, stat_type: str, ctx: Context) -> str:
    app = _ctx_app(ctx)
    repo = Repository(app.db)
    resolved = app.resolve_team_id(team_id)
    if stat_type == "pitching":
        rows = repo.pitching_splits(resolved)
    else:
        rows = repo.batting_splits(resolved)
    return json.dumps(rows, indent=2)


@mcp.resource("config://leagues")
def leagues_resource(ctx: Context) -> str:
    app = _ctx_app(ctx)
    return json.dumps([lg.model_dump() for lg in load_leagues(app.settings)], indent=2)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
