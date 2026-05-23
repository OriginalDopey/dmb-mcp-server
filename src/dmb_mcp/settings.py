"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIAMONDMIND = Path.home() / "Documents/CursonProjects/DiamondMind"


@dataclass(frozen=True)
class Settings:
    """Paths and context for the MCP server and CLI."""

    db_path: Path
    session_path: Path
    config_path: Path
    entry_team_id: str | None
    base_url: str = "https://www.imaginesports.com"
    request_delay: float = 1.5
    request_timeout: int = 30

    @classmethod
    def from_env(cls) -> Settings:
        dm = Path(os.environ.get("DMB_DIAMONDMIND_ROOT", str(DEFAULT_DIAMONDMIND)))
        pkg_root = Path(__file__).resolve().parents[2]
        return cls(
            db_path=Path(os.environ.get("DMB_DB_PATH", str(dm / "data" / "is_scout.db"))),
            session_path=Path(os.environ.get("DMB_SESSION_PATH", str(dm / ".is_session"))),
            config_path=Path(
                os.environ.get("DMB_CONFIG_PATH", str(pkg_root / "config" / "leagues.json"))
            ),
            entry_team_id=os.environ.get("DMB_ENTRY_TEAM_ID") or None,
        )


def get_settings() -> Settings:
    return Settings.from_env()


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]
