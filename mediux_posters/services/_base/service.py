__all__ = ["BaseService"]

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from mediux_posters.services._base.schemas import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)

T = TypeVar("T", bound=BaseShow)
S = TypeVar("S", bound=BaseSeason)
E = TypeVar("E", bound=BaseEpisode)
C = TypeVar("C", bound=BaseCollection)
M = TypeVar("M", bound=BaseMovie)


class BaseService(ABC, Generic[T, S, E, C, M]):
    @abstractmethod
    def list_shows(self, skip_libraries: list[str] | None = None) -> list[T]: ...

    @abstractmethod
    def get_show(self, tmdb_id: int) -> T | None: ...

    @abstractmethod
    def list_collections(self, skip_libraries: list[str] | None = None) -> list[C]: ...

    @abstractmethod
    def get_collection(self, tmdb_id: int) -> C | None: ...

    @abstractmethod
    def list_movies(self, skip_libraries: list[str] | None = None) -> list[M]: ...

    @abstractmethod
    def get_movie(self, tmdb_id: int) -> M | None: ...

    @abstractmethod
    def find(self, tmdb_id: int) -> T | C | M | None:
        return (
            self.get_show(tmdb_id=tmdb_id)
            or self.get_collection(tmdb_id=tmdb_id)
            or self.get_movie(tmdb_id=tmdb_id)
        )

    @abstractmethod
    def upload_posters(self, obj: T | S | E | M | C, kometa_integration: bool) -> None: ...
