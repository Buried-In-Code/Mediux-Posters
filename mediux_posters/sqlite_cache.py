__all__ = ["SQLiteCache"]

import sqlite3
from datetime import datetime
from pathlib import Path

from mediux_posters import get_cache_root


class SQLiteCache:
    def __init__(self, path: Path | None = None):
        self.connection = sqlite3.connect(path or get_cache_root() / "cache.sqlite")
        with self.connection as conn:
            conn.row_factory = sqlite3.Row

            conn.execute(
                "CREATE TABLE IF NOT EXISTS set_cache ("
                "set_id INT PRIMARY KEY, last_updated DATETIME NOT NULL"
                ");"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS file_cache ("
                "file_id TEXT PRIMARY KEY, last_updated DATETIME NOT NULL"
                ");"
            )

    def select_set(self, set_id: int) -> datetime | None:
        cursor = self.connection.execute(
            "SELECT last_updated FROM set_cache WHERE set_id = ?;", (set_id,)
        )
        if result := cursor.fetchone():
            return datetime.fromisoformat(result[0])
        return None

    def select_file(self, file_id: str) -> datetime | None:
        cursor = self.connection.execute(
            "SELECT last_updated FROM file_cache WHERE file_id = ?;", (file_id,)
        )
        if result := cursor.fetchone():
            return datetime.fromisoformat(result[0])
        return None

    def insert_set(self, set_id: int, last_updated: datetime) -> None:
        with self.connection as conn:
            conn.execute(
                "INSERT INTO set_cache (set_id, last_updated) VALUES (?, ?)"
                " ON CONFLICT(set_id) DO UPDATE SET last_updated = excluded.last_updated",
                (set_id, last_updated.isoformat()),
            )

    def insert_file(self, file_id: str, last_updated: datetime) -> None:
        with self.connection as conn:
            conn.execute(
                "INSERT INTO file_cache (file_id, last_updated) VALUES (?, ?)"
                " ON CONFLICT(file_id) DO UPDATE SET last_updated = excluded.last_updated",
                (file_id, last_updated.isoformat()),
            )
