"""League configuration loader."""

from __future__ import annotations

import json

from dmb_mcp.models import LeagueEntry
from dmb_mcp.settings import Settings, get_settings


def load_leagues(settings: Settings | None = None) -> list[LeagueEntry]:
    s = settings or get_settings()
    path = s.config_path
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    leagues = data.get("leagues", data if isinstance(data, list) else [])
    active_ids = set(data.get("active_entry_team_ids", []))
    out: list[LeagueEntry] = []
    for item in leagues:
        entry_id = item["entry_team_id"]
        out.append(
            LeagueEntry(
                entry_team_id=entry_id,
                display=item.get("display", entry_id),
                my_team_name=item.get("my_team_name", ""),
                key=item.get("key", ""),
                active=entry_id in active_ids if active_ids else item.get("active", True),
            )
        )
    return out


def active_leagues(settings: Settings | None = None) -> list[LeagueEntry]:
    return [lg for lg in load_leagues(settings) if lg.active]
