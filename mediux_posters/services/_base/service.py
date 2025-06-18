__all__ = ["BaseService"]

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from mediux_posters.services._base.schemas import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)
from mediux_posters.services.service_cache import ServiceCache
from mediux_posters.utils import MediaType

T = TypeVar("T", bound=BaseShow)
S = TypeVar("S", bound=BaseSeason)
E = TypeVar("E", bound=BaseEpisode)
C = TypeVar("C", bound=BaseCollection)
M = TypeVar("M", bound=BaseMovie)


class BaseService(ABC, Generic[T, S, E, C, M]):
    def __init__(self, cache: ServiceCache) -> None:
        self.cache = cache

    @abstractmethod
    def list_episodes(self, show_id: int | str, season_id: int | str) -> list[E]: ...

    @abstractmethod
    def list_seasons(self, show_id: int | str) -> list[S]: ...

    @abstractmethod
    def list_shows(self, skip_libraries: list[str] | None = None) -> list[T]: ...

    @abstractmethod
    def get_show(self, tmdb_id: int) -> T | None: ...

    @abstractmethod
    def list_collections(self, skip_libraries: list[str] | None = None) -> list[C]: ...

    @abstractmethod
    def get_collection(self, tmdb_id: int) -> C | None: ...

    @abstractmethod
    def list_collection_movies(self, collection_id: int | str) -> list[M]: ...

    @abstractmethod
    def list_movies(self, skip_libraries: list[str] | None = None) -> list[M]: ...

    @abstractmethod
    def get_movie(self, tmdb_id: int) -> M | None: ...

    def list(
        self, media_type: MediaType, skip_libraries: list[str] | None = None
    ) -> list[T] | list[C] | list[M]:
        skip_libraries = skip_libraries or []
        return (
            self.list_shows(skip_libraries=skip_libraries)
            if media_type is MediaType.SHOW
            else self.list_collections(skip_libraries=skip_libraries)
            if media_type is MediaType.COLLECTION
            else self.list_movies(skip_libraries=skip_libraries)
            if media_type is MediaType.MOVIE
            else []
        )

    def get(self, media_type: MediaType, tmdb_id: int) -> T | C | M | None:
        return (
            self.get_show(tmdb_id=tmdb_id)
            if media_type is MediaType.SHOW
            else self.get_collection(tmdb_id=tmdb_id)
            if media_type is MediaType.COLLECTION
            else self.get_movie(tmdb_id=tmdb_id)
            if media_type is MediaType.MOVIE
            else None
        )

    @abstractmethod
    def upload_image(
        self, object_id: int | str, image_file: Path, kometa_integration: bool
    ) -> bool: ...
