__all__ = ["BaseCollection", "BaseEpisode", "BaseMovie", "BaseSeason", "BaseSeries", "BaseService"]

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

from pydantic import Field

from mediux_posters.utils import BaseModel, MediaType


class BaseEpisode(BaseModel):
    mediatype: ClassVar[MediaType] = MediaType.EPISODE
    id: str | int
    number: int

    title_card: Path | None = None
    title_card_uploaded: bool = False

    @property
    def all_posters_uploaded(self) -> bool:
        return self.title_card_uploaded


class BaseSeason(BaseModel):
    mediatype: ClassVar[MediaType] = MediaType.SEASON
    id: str | int
    number: int
    episodes: list[BaseEpisode] = Field(default_factory=list)

    poster: Path | None = None
    poster_uploaded: bool = False

    @property
    def all_posters_uploaded(self) -> bool:
        return self.poster_uploaded and all(x.all_posters_uploaded for x in self.episodes)


class BaseSeries(BaseModel):
    mediatype: ClassVar[MediaType] = MediaType.SERIES
    id: str | int
    name: str
    year: int
    tmdb_id: int
    seasons: list[BaseSeason] = Field(default_factory=list)

    poster: Path | None = None
    poster_uploaded: bool = False
    backdrop: Path | None = None
    backdrop_uploaded: bool = False

    @property
    def display_name(self) -> str:
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and all(x.all_posters_uploaded for x in self.seasons)
        )


class BaseMovie(BaseModel):
    mediatype: ClassVar[MediaType] = MediaType.MOVIE
    id: str | int
    name: str
    year: int
    tmdb_id: int

    poster: Path | None = None
    poster_uploaded: bool = False
    backdrop: Path | None = None
    backdrop_uploaded: bool = False

    @property
    def display_name(self) -> str:
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return self.poster_uploaded and self.backdrop_uploaded


class BaseCollection(BaseModel):
    mediatype: ClassVar[MediaType] = MediaType.COLLECTION
    id: str | int
    name: str
    tmdb_id: int
    movies: list[BaseMovie] = Field(default_factory=list)

    poster: Path | None = None
    poster_uploaded: bool = False
    backdrop: Path | None = None
    backdrop_uploaded: bool = False

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and all(x.all_posters_uploaded for x in self.movies)
        )


T = TypeVar("T", bound=BaseSeries)
S = TypeVar("S", bound=BaseSeason)
E = TypeVar("E", bound=BaseEpisode)
M = TypeVar("M", bound=BaseMovie)
C = TypeVar("C", bound=BaseCollection)


class BaseService(ABC, Generic[T, S, E, M, C]):
    @abstractmethod
    def list_series(self, exclude_libraries: list[str] | None = None) -> list[T]: ...

    @abstractmethod
    def get_series(self, tmdb_id: int) -> T | None: ...

    @abstractmethod
    def list_movies(self, exclude_libraries: list[str] | None = None) -> list[M]: ...

    @abstractmethod
    def get_movie(self, tmdb_id: int) -> M | None: ...

    @abstractmethod
    def list_collections(self, exclude_libraries: list[str] | None = None) -> list[C]: ...

    @abstractmethod
    def get_collection(self, tmdb_id: int) -> C | None: ...

    @abstractmethod
    def upload_posters(self, obj: T | S | E | M | C) -> None: ...