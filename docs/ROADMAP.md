# Roadmap

**Status: v0.1** — functional MCP server with offline parser tests and typed SQLite queries. Not affiliated with ImagineSports.

## Done

- [x] FastMCP server with 6 tools and 11 resources
- [x] Incremental scrape modes (`full`, `refresh`, `tracker`)
- [x] Extended page parsers (leaderboards, injuries, splits, league transactions, …)
- [x] Offline HTML fixture tests for parsers
- [x] Repository layer with in-memory unit tests
- [x] Public-safe config pattern (`leagues.example.json`; real config gitignored)
- [x] Architecture and write-ops spike docs

## In progress

- [x] GitHub Actions CI on `main` (pytest + ruff + SBOM artifact)
- [ ] Broader test coverage (scraper orchestration, reference service)
- [ ] `uv.lock` for fully reproducible CI installs

## Planned

- [ ] MCP integration tests via official SDK client
- [ ] Box score scrape (game ID discovery from daily recap)
- [ ] Write operations spike → optional guarded lineup/rotation POST tools
- [ ] Refactor `_*_body.py` exec modules into normal imports (long-term cleanup)

## Out of scope

- Play-by-play scraping
- Player search / DMO downloads
- ImagineSports account automation beyond session cookie
