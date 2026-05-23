"""SQLite database layer for ImagineSports scouting data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dmb_mcp.settings import Settings, package_root

SCHEMA_SQL = (package_root() / "migrations" / "001_initial_schema.sql").read_text()
MIGRATION_002_SQL = (package_root() / "migrations" / "002_extended_tables.sql").read_text()


def _load_database_class() -> type:
    body_path = Path(__file__).with_name("_database_body.py")
    namespace: dict = {
        "sqlite3": sqlite3,
        "Path": Path,
        "datetime": datetime,
        "timezone": timezone,
        "SCHEMA_SQL": SCHEMA_SQL,
        "DB_PATH": None,
    }
    exec(body_path.read_text(), namespace)
    return namespace["Database"]


_Database = _load_database_class()


class Database(_Database):
    """Database with settings-aware default path."""

    def __init__(self, db_path: str | Path | None = None, settings: Settings | None = None):
        if db_path is None:
            db_path = (settings or Settings.from_env()).db_path
        super().__init__(db_path=db_path)
        self._apply_extended_migration()

    def _apply_extended_migration(self) -> None:
        self.conn.executescript(MIGRATION_002_SQL)
        self.conn.commit()
