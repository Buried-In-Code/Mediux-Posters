__all__ = ["ServiceCache"]

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from mediux_posters import get_cache_root
from mediux_posters.mediux import FileType


@dataclass(kw_only=True)
class CacheData:
    creator: str
    set_id: int
    last_updated: datetime


class ServiceCache:
    def __init__(self, service: str) -> None:
        self._db_path = get_cache_root() / f"{service}.sqlite"
        self.initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        conn = None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            if conn:
                conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    creator TEXT NOT NULL,
                    set_id INTEGER NOT NULL,
                    last_updated TIMESTAMP NOT NULL,
                    PRIMARY KEY (id, type)
                );
                """
            )

    def select(self, object_id: int | str, file_type: FileType) -> CacheData | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT creator, set_id, last_updated FROM cache WHERE id = ? AND type = ?;",
                (str(object_id), str(file_type)),
            ).fetchone()
            return (
                CacheData(
                    creator=row["creator"],
                    set_id=row["set_id"],
                    last_updated=datetime.fromisoformat(row["last_updated"]),
                )
                if row
                else None
            )

    def insert(
        self,
        object_id: int | str,
        file_type: FileType,
        creator: str,
        set_id: int,
        last_updated: datetime,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (
                    id, type, creator, set_id, last_updated
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (str(object_id), str(file_type), creator, set_id, last_updated.isoformat()),
            )

    def delete(self, object_id: int | str, file_type: FileType) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM cache WHERE id = ? AND type = ?;", (str(object_id), str(file_type))
            )
