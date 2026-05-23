"""Database helpers for extended scrape tables."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from dmb_mcp.db.database import Database


def replace_league_rows(
    db: Database, table: str, league_id: str, rows: list[dict[str, Any]]
) -> int:
    db.execute(f"DELETE FROM {table} WHERE league_id = ?", [league_id])
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    db.executemany(
        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    return len(rows)


def replace_team_rows(db: Database, table: str, team_id: str, rows: list[dict[str, Any]]) -> int:
    db.execute(f"DELETE FROM {table} WHERE team_id = ?", [team_id])
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    db.executemany(
        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    return len(rows)


def upsert_park_reference(db: Database, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    for row in rows:
        db.execute(
            """
            INSERT INTO park_reference
                (park_name, scraped_at, years, city, surface, cover,
                 dimensions_json, factors_lhb_json, factors_rhb_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(park_name) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                years = excluded.years,
                city = excluded.city,
                surface = excluded.surface,
                cover = excluded.cover,
                dimensions_json = excluded.dimensions_json,
                factors_lhb_json = excluded.factors_lhb_json,
                factors_rhb_json = excluded.factors_rhb_json
            """,
            [
                row["park_name"],
                row["scraped_at"],
                row.get("years", ""),
                row.get("city", ""),
                row.get("surface", ""),
                row.get("cover", ""),
                row.get("dimensions_json", "{}"),
                row.get("factors_lhb_json", "{}"),
                row.get("factors_rhb_json", "{}"),
            ],
        )
    return len(rows)


def replace_record_boards(db: Database, board_key: str, rows: list[dict[str, Any]]) -> int:
    db.execute("DELETE FROM record_boards WHERE board_key = ?", [board_key])
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    db.executemany(
        f"INSERT INTO record_boards ({col_names}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    return len(rows)


def get_reference_cache(db: Database, cache_key: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT payload_json, expires_at FROM reference_cache WHERE cache_key = ?",
        [cache_key],
    ).fetchone()
    if not row:
        return None
    expires = row["expires_at"]
    if expires:
        exp_dt = datetime.fromisoformat(expires)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=UTC)
        if datetime.now(UTC) > exp_dt:
            return None
    return json.loads(row["payload_json"])


def set_reference_cache(
    db: Database,
    cache_key: str,
    payload: dict[str, Any],
    *,
    ttl_days: int = 7,
) -> None:
    now = datetime.now(UTC)
    expires = now + timedelta(days=ttl_days)
    db.execute(
        """
        INSERT INTO reference_cache (cache_key, scraped_at, expires_at, payload_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            scraped_at = excluded.scraped_at,
            expires_at = excluded.expires_at,
            payload_json = excluded.payload_json
        """,
        [cache_key, now.isoformat(), expires.isoformat(), json.dumps(payload)],
    )


def park_reference_count(db: Database) -> int:
    row = db.execute("SELECT COUNT(*) AS c FROM park_reference").fetchone()
    return int(row["c"]) if row else 0
