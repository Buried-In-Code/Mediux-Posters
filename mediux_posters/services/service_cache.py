__all__ = ["CacheKey", "ServiceCache"]

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from mediux_posters import get_cache_root
from mediux_posters.mediux import FileType

CACHE_QUERY: Final[str] = "tmdb_id = ? AND season_num = ? AND episode_num = ? AND type = ?"


@dataclass(kw_only=True)
class CacheKey:
    tmdb_id: int
    season_num: int = 0
    episode_num: int = 0
    type: FileType

    def as_tuple(self) -> tuple[int, int, int, str]:
        return (self.tmdb_id, self.season_num, self.episode_num, str(self.type))


@dataclass(kw_only=True)
class CacheData:
    creator: str
    set_id: int
    last_updated: datetime
    plex_uploaded: datetime | None = None
    jellyfin_uploaded: datetime | None = None


class ServiceCache:
    def __init__(self) -> None:
        self._db_path = get_cache_root() / "cache.sqlite"
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
                    tmdb_id INTEGER NOT NULL,
                    season_num INTEGER NULL,
                    episode_num INTEGER NULL,
                    type TEXT NOT NULL,
                    creator TEXT NOT NULL,
                    set_id INTEGER NOT NULL,
                    last_updated TIMESTAMP NOT NULL,
                    plex_uploaded TIMESTAMP NULL,
                    jellyfin_uploaded TIMESTAMP NULL,
                    PRIMARY KEY (tmdb_id, season_num, episode_num, type)
                );
                """
            )
            conn.commit()

    def select(self, key: CacheKey) -> CacheData | None:
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT creator, set_id, last_updated, plex_uploaded, jellyfin_uploaded
                FROM cache
                WHERE {CACHE_QUERY};
                """,  # noqa: S608
                key.as_tuple(),
            ).fetchone()
            if not row:
                return None
            return CacheData(
                creator=row["creator"],
                set_id=row["set_id"],
                last_updated=datetime.fromisoformat(row["last_updated"]),
                plex_uploaded=datetime.fromisoformat(row["plex_uploaded"])
                if row["plex_uploaded"]
                else None,
                jellyfin_uploaded=datetime.fromisoformat(row["jellyfin_uploaded"])
                if row["jellyfin_uploaded"]
                else None,
            )

    def get_timestamp(self, key: CacheKey, service: Literal["Plex", "Jellyfin"]) -> datetime | None:
        service = service.lower()
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT {service}_uploaded
                FROM cache
                WHERE {CACHE_QUERY};
                """,  # noqa: S608
                key.as_tuple(),
            ).fetchone()
            if not row or not row[f"{service}_uploaded"]:
                return None
            return datetime.fromisoformat(row[f"{service}_uploaded"])

    def insert(self, key: CacheKey, creator: str, set_id: int, last_updated: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache (
                    tmdb_id, season_num, episode_num, type, creator, set_id, last_updated, plex_uploaded, jellyfin_uploaded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (*key.as_tuple(), creator, set_id, last_updated.isoformat(), None, None),
            )
            conn.commit()

    def update(self, key: CacheKey, creator: str, set_id: int, last_updated: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE cache
                SET creator = ?, set_id = ?, last_updated = ?
                WHERE {CACHE_QUERY};
                """,  # noqa: S608
                (creator, set_id, last_updated.isoformat(), *key.as_tuple()),
            )
            conn.commit()

    def update_service(
        self, key: CacheKey, service: Literal["Plex", "Jellyfin"], timestamp: datetime | None
    ) -> None:
        service = service.lower()
        with self._connect() as conn:
            set_clause = f"{service}_uploaded = ?"
            value = timestamp.isoformat() if timestamp else None

            conn.execute(
                f"""
                UPDATE cache
                SET {set_clause}
                WHERE {CACHE_QUERY};
                """,  # noqa: S608
                (value, *key.as_tuple()),
            )
            conn.commit()

    def delete(self, key: CacheKey) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                DELETE FROM cache
                WHERE {CACHE_QUERY};
                """,  # noqa: S608
                key.as_tuple(),
            )
            conn.commit()
