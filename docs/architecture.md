# Architecture

## Layers

1. **FastMCP server** (`server.py`) — tools, resources, lifespan
2. **Context** (`context.py`) — resolves `mine` scoping via `DMB_ENTRY_TEAM_ID`
3. **Repository** (`db/repository.py`) — typed read queries over SQLite
4. **Scraper engine** (`scraper/`) — extracted from DiamondMind `is_league_scraper.py`
5. **SQLite** (`migrations/001_initial_schema.sql`, `002_extended_tables.sql`) — shared with DiamondMind `data/is_scout.db`
6. **Extended scrape** (`scraper/extended_scrape.py`, `parsers/extended.py`) — leaderboards, fielding leaders, team-vs-team, league transactions, injuries, splits, trade view
7. **Reference service** (`reference.py`) — park reference (live + cache), 2026 record boards (live or static fallback)

## Scrape modes

| Mode | Behavior |
|------|----------|
| `full` | Legacy full scrape + extended pages (leaderboards, splits, team-vs-team, etc.) |
| `refresh` | Incremental standings + weekly stats/rosters/transactions + injuries + league transactions |
| `tracker` | Standings-only minimal path (no extended pages) |

## Extended page tiers

| Tier | Pages |
|------|-------|
| Every refresh | injuries, league transactions |
| Full only | leaderboards, fielding leaders, team-vs-team, trade view, batting/pitching splits |
| Reference tool | parks (cache), record boards (weekly cache + static fallback) |

Standings history uses `cutoff_game_id` walk with cache stop at last stored `game_id`.

## Team workspaces

Each team folder gets `.cursor/mcp.json` with `DMB_ENTRY_TEAM_ID`. Resources like `standings://mine` resolve to that league/team.
