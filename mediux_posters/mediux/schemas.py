__all__ = [
    "Collection",
    "CollectionSet",
    "Episode",
    "FileType",
    "Movie",
    "MovieSet",
    "Season",
    "Show",
    "ShowSet",
]

from datetime import date, datetime
from enum import Enum

from pydantic import AliasPath, Field

from mediux_posters.utils import BaseModel


class MediuxModel(BaseModel, extra="ignore"): ...


class FileType(str, Enum):
    ALBUM = "album"
    BACKDROP = "backdrop"
    LOGO = "logo"
    MISC = "misc"
    POSTER = "poster"
    TITLE_CARD = "titlecard"


class File(MediuxModel):
    id: str
    file_type: FileType
    show_id: int | None = Field(validation_alias=AliasPath("show", "id"), default=None)
    season_id: int | None = Field(validation_alias=AliasPath("season", "id"), default=None)
    episode_id: int | None = Field(validation_alias=AliasPath("episode", "id"), default=None)
    collection_id: int | None = Field(validation_alias=AliasPath("collection", "id"), default=None)
    movie_id: int | None = Field(validation_alias=AliasPath("movie", "id"), default=None)


class Episode(MediuxModel):
    date_updated: datetime | None
    id: int
    number: int = Field(alias="episode_number")
    title: str = Field(alias="episode_title")


class Season(MediuxModel):
    date_updated: datetime | None
    episodes: list[Episode]
    id: int
    number: int = Field(alias="season_number")
    title: str = Field(alias="season_name")


class Show(MediuxModel):
    date_updated: datetime | None
    release_date: date | None = Field(alias="first_air_date")
    seasons: list[Season]
    title: str
    tmdb_id: int = Field(alias="id")


class ShowSet(MediuxModel):
    date_created: datetime
    date_updated: datetime | None
    files: list[File]
    id: int
    set_title: str
    show: Show = Field(alias="show_id")
    username: str = Field(validation_alias=AliasPath("user_created", "username"))


class Movie(MediuxModel):
    date_updated: datetime | None
    release_date: date | None
    title: str
    tmdb_id: int = Field(alias="id")


class MovieSet(MediuxModel):
    date_created: datetime
    date_updated: datetime | None
    files: list[File]
    id: int
    movie: Movie = Field(alias="movie_id")
    set_title: str
    username: str = Field(validation_alias=AliasPath("user_created", "username"))


class Collection(MediuxModel):
    date_updated: datetime | None
    movies: list[Movie]
    title: str = Field(alias="collection_name")
    tmdb_id: int = Field(alias="id")


class CollectionSet(MediuxModel):
    collection: Collection = Field(alias="collection_id")
    date_created: datetime
    date_updated: datetime | None
    files: list[File]
    id: int
    set_title: str
    username: str = Field(validation_alias=AliasPath("user_created", "username"))
