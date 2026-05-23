# Write Operations Spike — Edit Lineup

**Date:** 2026-05-23  
**Target:** `https://imaginesports.com/bball/manage/edit_lineup`  
**Goal:** Assess whether HTTP form POSTs can replace browser MCP for roster configuration writes.

## Method

Authenticated GET via `ISSession` using a local session file (see `.env.example`), entry team from `DMB_ENTRY_TEAM_ID`.

## Findings

### Page loads with session

- URL pattern: `/bball/manage/edit_lineup?curTeam=<entry_team_id>`
- Returns HTML form with lineup dropdown, nine batting slots, position assignments, and **Save this Lineup** submit control.
- Requires valid session cookie; unauthenticated requests redirect to login (`AUTH_REQUIRED`).

### Form structure (typical IS manage screen)

- **Lineup selector** — dropdown naming lineups (`Primary vs. LHP`, `Primary vs. RHP`, etc.).
- **Nine rows** — batting order slots with player `<select>` elements and position fields.
- **Hidden/context fields** — `curTeam`, lineup name/id, and other IS-specific tokens present in form action URL or hidden inputs (inspect per save).
- **Save button** — POST back to manage endpoint (exact action URL varies by screen state).

### POST feasibility

| Aspect | Assessment |
|--------|------------|
| Auth | Works with saved `.is_session` cookie |
| CSRF token | **Not observed** as a separate CSRF field in initial GET; IS may rely on session + curTeam scoping |
| JavaScript requirement | Form appears server-rendered; no obvious SPA-only save path |
| Validation | Server enforces roster eligibility, position coverage, and minimum fielding rules |
| Risk | Undocumented hidden fields may change; lineup name must match existing slot |

### Recommendation

**Phase 3 candidate — medium complexity.**

1. Implement `GET edit_lineup` parser to extract form fields + current selections.
2. Implement `POST edit_lineup` with explicit lineup name, batting order array, and positions.
3. Verify by re-GET and diff against intended lineup.
4. Start with **read-only form export** tool before enabling writes in MCP.

Lower-risk write targets to prototype first:

- `/bball/manage/pitch_rotation` (4–5 SP slots)
- `/bball/manage/team_tendencies` (numeric 1–5 scales)

Defer high-risk flows (cash worksheet, trades) until lineup POST is proven stable.

## Next steps

- [ ] Capture full form HTML fixture on save attempt (network tab or scripted POST)
- [ ] Add `dmb_mcp.write.lineup` module behind explicit `DMB_ENABLE_WRITES=1` guard
- [ ] Never expose write tools until round-trip verification passes in CI with mock forms
