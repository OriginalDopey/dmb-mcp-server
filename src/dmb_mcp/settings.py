"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
        pkg_root = package_root()
        data_dir = pkg_root / "data"
        config_path = pkg_root / "config" / "leagues.json"
        if not config_path.exists():
            config_path = pkg_root / "config" / "leagues.example.json"

        db_default = data_dir / "is_scout.db"
        session_default = pkg_root / ".is_session"

        return cls(
            db_path=Path(os.environ.get("DMB_DB_PATH", str(db_default))),
            session_path=Path(os.environ.get("DMB_SESSION_PATH", str(session_default))),
            config_path=Path(os.environ.get("DMB_CONFIG_PATH", str(config_path))),
            entry_team_id=os.environ.get("DMB_ENTRY_TEAM_ID") or None,
        )


def get_settings() -> Settings:
    return Settings.from_env()


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]
