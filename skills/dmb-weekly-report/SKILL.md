---
name: dmb-weekly-report
description: >-
  Generate a weekly league intelligence report using dmb-mcp-server scrape + query
  tools. Use for end-of-week recaps, FA activity summaries, injury checks, or
  standings movement across an active Classic Standard league.
---

# DMB Weekly Report

## When to use

- User wants a weekly league snapshot or FA/injury/standings recap.
- End of IS week (Saturday payment / Sunday off-day window).
- Before making in-season transaction decisions.

## Workflow

1. **Refresh data** (scoped to team workspace):

```
scrape(mode="refresh")
```

Or all active leagues:

```
scrape_all(mode="refresh")
```

2. **Pull core context**:

| Query | Purpose |
|-------|---------|
| `query(type="standings", target_id="mine")` | Division race, RS/RA, streaks |
| `query(type="league_transactions", target_id="mine", options={"limit": 25})` | League-wide FA/trades |
| `query(type="injuries", target_id="mine")` | Current IL status |
| `query(type="financials", target_id="mine")` | Cash, cap headroom |

3. **Optional full-mode extras** (run `scrape(mode="full")` weekly or biweekly):

- `query(type="leaderboards", target_id="mine")`
- `query(type="team_vs_team", target_id="mine")`
- `query(type="splits", target_id="mine", options={"stat_type":"batting"})`

4. **Report tool**:

```
report(type="league_summary", target_id="mine")
report(type="team_snapshot", target_id="mine")
```

## Output structure

Write a concise markdown note in the team folder:

1. **Standings** — W-L, GB, RS/RA, L10
2. **Bankroll** — cash, roster salary, upcoming payment if visible
3. **Injuries** — who is out, replacements in play
4. **Transactions** — notable league moves (FA sign/release, loans)
5. **Watch list** — 2–3 actionable observations

## Timing tip

Execute refreshes **after noon PT, before Game 3** when possible to maximize interest on positive cash balance (Classic Standard).
