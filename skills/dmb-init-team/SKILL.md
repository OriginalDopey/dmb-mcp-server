---
name: dmb-init-team
description: >-
  Scaffold a Diamond Mind Baseball team workspace with MCP scoping via
  DMB_ENTRY_TEAM_ID. Use when setting up a new team folder, wiring .cursor/mcp.json,
  or onboarding a league entry to the dmb-mcp-server tools.
---

# DMB Init Team Workspace

## When to use

- User creates a new `Teams/<TeamName>_2026/` folder.
- User asks to wire MCP for a league entry team ID.
- User wants team-scoped `mine` aliases for standings/roster/scrape.

## Steps

1. Get **entry team ID** (`curTeam=` from any ImagineSports league URL).
2. Run from the `dmb-mcp-server` repo:

```bash
python3.11 -m dmb_mcp.cli init-team "Team Display Name" \
  --entry-team-id <ENTRY_TEAM_ID> \
  --team-dir /path/to/my-team-workspace \
  --diamondmind-root /path/to/project-root
```

3. Verify `.cursor/mcp.json` sets `DMB_ENTRY_TEAM_ID`.
4. Open the team folder in Cursor and test:
   - `auth(action="status")`
   - `scrape(mode="refresh")`
   - `query(type="standings", target_id="mine")`

## What gets created

- `.cursor/mcp.json` — MCP server + env paths
- `.cursor/rules/team-context.mdc` — always-on team scope reminder
- `README.md` — stub if missing

## Notes

- One SQLite DB (`data/is_scout.db` by default) holds all leagues.
- Session cookie: `.is_session` in your project root (never commit this file).
- Use `uv` if installed; otherwise `python3.11 -m pip install -e ".[dev]"` in `dmb-mcp-server`.
