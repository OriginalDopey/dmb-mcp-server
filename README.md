# dmb-mcp-server

A **Model Context Protocol (MCP) server** that gives AI coding agents structured access to [ImagineSports / Diamond Mind Baseball](https://www.imaginesports.com) league data: standings, rosters, transactions, leaderboards, injuries, and reference tables.

Built with **FastMCP**, **Pydantic**, **SQLite**, and **BeautifulSoup** — designed for incremental scraping, typed query surfaces, and team-scoped agent workspaces.

[![CI](https://github.com/OriginalDopey/dmb-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/OriginalDopey/dmb-mcp-server/actions/workflows/ci.yml)

## Highlights

- **6 MCP tools** + **11 resources** — scrape, query, report, auth, and reference data without bloating agent context
- **Incremental scrape engine** — game-by-game standings cache; refresh vs full vs tracker modes
- **Team scoping** — `DMB_ENTRY_TEAM_ID` resolves `mine` aliases for league/team resources
- **Parser test suite** — offline HTML fixtures; no live credentials required to run tests
- **CI** — ruff, pytest, CycloneDX SBOM artifact

## Quick start

Requires **Python 3.11+**.

```bash
git clone https://github.com/originaldopey/dmb-mcp-server.git
cd dmb-mcp-server
python3.11 -m pip install -e ".[dev]"

cp config/leagues.example.json config/leagues.json
# Edit config/leagues.json with your entry team ID(s)

export DMB_DB_PATH="$PWD/data/is_scout.db"
export DMB_SESSION_PATH="$PWD/.is_session"
export DMB_CONFIG_PATH="$PWD/config/leagues.json"

python3.11 -m dmb_mcp.cli auth --cookie "session=YOUR_COOKIE"
python3.11 -m dmb_mcp.cli scrape --entry-team-id YOUR_ENTRY_TEAM_ID --mode refresh
python3.11 -m dmb_mcp.server   # stdio MCP server
```

> **Security:** Never commit `.is_session`, `.env`, or `config/leagues.json`. Session cookies are local-only credentials.

## Cursor MCP config

```json
{
  "mcpServers": {
    "dmb": {
      "command": "python3.11",
      "args": ["-m", "dmb_mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/dmb-mcp-server/src",
        "DMB_DB_PATH": "/path/to/data/is_scout.db",
        "DMB_SESSION_PATH": "/path/to/.is_session",
        "DMB_CONFIG_PATH": "/path/to/dmb-mcp-server/config/leagues.json",
        "DMB_ENTRY_TEAM_ID": "YOUR_ENTRY_TEAM_ID"
      }
    }
  }
}
```

## Init a team workspace

```bash
python3.11 -m dmb_mcp.cli init-team "My Team 2026" \
  --entry-team-id YOUR_ENTRY_TEAM_ID \
  --team-dir ./my-team-workspace
```

## MCP tools

| Tool | Purpose |
|------|---------|
| `auth` | Set or validate session cookie |
| `scrape` | Scrape one league (`full` / `refresh` / `tracker`) |
| `scrape_all` | Scrape all active leagues in config |
| `query` | Read cached DB (standings, roster, leaderboards, injuries, splits, …) |
| `report` | Human-readable league summary or team snapshot |
| `reference` | Park reference and 2026 Standard record boards |

## MCP resources

| URI | Data |
|-----|------|
| `standings://{league_id}` | Current standings |
| `roster://{team_id}` | Roster + salaries |
| `financials://{team_id}` | Cash / payroll |
| `rules://{league_id}` | League rules |
| `transactions://{league_id}` | Team transaction log |
| `leaderboards://{league_id}/{board_type}` | Batting or pitching leaderboards |
| `injuries://{team_id}` | Injury list |
| `splits://{team_id}/{stat_type}` | Batting or pitching splits |
| `config://leagues` | League config |

Use `mine` instead of an ID when `DMB_ENTRY_TEAM_ID` is set.

## Development

```bash
python3.11 -m pytest
python3.11 -m ruff check src tests/
```

See [docs/architecture.md](docs/architecture.md) for scrape tiers and module layout.

## License

MIT — see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
