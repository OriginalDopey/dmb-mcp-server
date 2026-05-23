---
name: dmb-team-snapshot
description: >-
  Quick team snapshot from dmb-mcp-server cached data: roster, finances, injuries,
  recent transactions. Use when user asks "where am I at?", roster audit, or
  pre-lineup-change context for their DMB team.
---

# DMB Team Snapshot

## When to use

- Quick status check without a full league recap.
- Before lineup/bench/rotation changes.
- Verifying post-transaction roster state.

## Minimal flow

1. If data may be stale (>24h): `scrape(mode="refresh")`
2. Run:

```
report(type="team_snapshot", target_id="mine")
query(type="roster", target_id="mine")
query(type="financials", target_id="mine")
query(type="injuries", target_id="mine")
```

3. Optional platoon context:

```
query(type="splits", target_id="mine", options={"stat_type":"batting"})
query(type="splits", target_id="mine", options={"stat_type":"pitching"})
```

## Resources (read-only)

- `roster://mine`
- `financials://mine`
- `injuries://mine`
- `splits://mine/batting`

## Output

Short bullet summary:

- **Record / place** (from standings resource if needed)
- **Cash / payroll**
- **Injuries**
- **Roster holes** (positions, IR, minimum salary depth)
- **One-line recommendation** if obvious (e.g., catcher fatigue, missing platoon)
