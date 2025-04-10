__all__ = ["Collection", "Episode", "Library", "Movie", "Season", "Show"]

from datetime import date, datetime
from typing import Literal

from pydantic import AliasPath, Field, field_validator
from pydantic.alias_generators import to_pascal

from mediux_posters.services._base import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)
from mediux_posters.utils import BaseModel


class JellyfinModel(BaseModel, alias_generator=to_pascal, extra="ignore"): ...


class Library(JellyfinModel):
    id: str
    title: str = Field(alias="Name")
    type: Literal["movies", "tvshows", "unknown"] = Field(alias="CollectionType")


class Episode(BaseEpisode, JellyfinModel):
    imdb_id: str | None = Field(validation_alias=AliasPath("ProviderIds", "Imdb"), default=None)
    number: int = Field(alias="IndexNumber")
    tmdb_id: int | None = Field(validation_alias=AliasPath("ProviderIds", "Tmdb"), default=None)
    tv_maze_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvMaze"), default=None
    )
    tv_rage_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvRage"), default=None
    )
    tvdb_id: int | None = Field(validation_alias=AliasPath("ProviderIds", "Tvdb"), default=None)

    @field_validator("premiere_date", mode="before")
    def datetime_to_date(cls, value: str | datetime | date | None) -> str | datetime | date | None:
        if not value:
            return None
        if isinstance(value, str):
            return value.split("T")[0]
        return value


class Season(BaseSeason, JellyfinModel):
    imdb_id: str | None = Field(validation_alias=AliasPath("ProviderIds", "Imdb"), default=None)
    number: int = Field(alias="IndexNumber")
    tmdb_id: int | None = Field(validation_alias=AliasPath("ProviderIds", "Tmdb"), default=None)
    tv_maze_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvMaze"), default=None
    )
    tv_rage_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvRage"), default=None
    )
    tvdb_id: int | None = Field(validation_alias=AliasPath("ProviderIds", "Tvdb"), default=None)

    @field_validator("premiere_date", mode="before")
    def datetime_to_date(cls, value: str | datetime | date | None) -> str | datetime | date | None:
        if not value:
            return None
        if isinstance(value, str):
            return value.split("T")[0]
        return value


class Show(BaseShow, JellyfinModel):
    imdb_id: str | None = Field(validation_alias=AliasPath("ProviderIds", "Imdb"), default=None)
    tmdb_id: int = Field(validation_alias=AliasPath("ProviderIds", "Tmdb"))
    tv_maze_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvMaze"), default=None
    )
    tv_rage_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TvRage"), default=None
    )
    tvdb_id: int | None = Field(validation_alias=AliasPath("ProviderIds", "Tvdb"), default=None)
    year: int = Field(alias="ProductionYear")

    @field_validator("premiere_date", mode="before")
    def datetime_to_date(cls, value: str | datetime | date | None) -> str | datetime | date | None:
        if not value:
            return None
        if isinstance(value, str):
            return value.split("T")[0]
        return value


class Movie(BaseMovie, JellyfinModel):
    imdb_id: str = Field(validation_alias=AliasPath("ProviderIds", "Imdb"))
    tmdb_collection_id: int | None = Field(
        validation_alias=AliasPath("ProviderIds", "TmdbCollection"), default=None
    )
    tmdb_id: int = Field(validation_alias=AliasPath("ProviderIds", "Tmdb"))
    year: int = Field(alias="ProductionYear")

    @field_validator("premiere_date", mode="before")
    def datetime_to_date(cls, value: str | datetime | date | None) -> str | datetime | date | None:
        if not value:
            return None
        if isinstance(value, str):
            return value.split("T")[0]
        return value


class Collection(BaseCollection, JellyfinModel):
    pass
