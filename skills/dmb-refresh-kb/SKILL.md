---
name: dmb-refresh-kb
description: Refresh ImagineSports league data via the dmb MCP server, then summarize standings and recent activity for scoped team/league. Use when the user says refresh kb, refresh my data, update league data, or sync ImagineSports.
---

# dmb-refresh-kb

## Workflow

1. Call MCP tool `auth` with `action=status`. If invalid, ask user for cookie and call `auth` with `action=set_cookie`.
2. Call `scrape` with `mode=refresh` (uses `DMB_ENTRY_TEAM_ID` when set) OR `scrape_all` for all active leagues.
3. Read resources:
   - `standings://mine`
   - `financials://mine`
   - `transactions://mine` (via `query` type=transactions if needed)
4. Call `report` with `type=league_summary` and `target_id=mine`.
5. Return a concise state-of-the-world summary: record, division standing, cash, last 3 transactions.

## Notes

- Do not commit or log session cookies.
- Trust incremental standings cache; refresh only pulls new game snapshots.
