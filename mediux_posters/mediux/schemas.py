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
from typing import Annotated

from pydantic import AliasPath, BeforeValidator, Field, TypeAdapter, ValidationError

from mediux_posters.utils import BaseModel


def int_or_str(val: int | str | None) -> int | str | None:
    try:
        return TypeAdapter(int).validate_python(val)
    except ValidationError:
        return val


class MediuxModel(BaseModel, extra="ignore"): ...


class FileType(str, Enum):
    ALBUM = "album"
    BACKDROP = "backdrop"
    LOGO = "logo"
    MISC = "misc"
    POSTER = "poster"
    TITLE_CARD = "titlecard"

    def __str__(self) -> str:
        return self.value


class File(MediuxModel):
    id: str
    file_type: FileType
    last_updated: datetime = Field(alias="modified_on")
    show_id: Annotated[int | None, Field(validation_alias=AliasPath("show", "id"))] = None
    season_id: Annotated[
        int | str | None,
        BeforeValidator(int_or_str),
        Field(validation_alias=AliasPath("season", "id")),
    ] = None
    episode_id: Annotated[int | None, Field(validation_alias=AliasPath("episode", "id"))] = None
    collection_id: Annotated[int | None, Field(validation_alias=AliasPath("collection", "id"))] = (
        None
    )
    movie_id: Annotated[int | None, Field(validation_alias=AliasPath("movie", "id"))] = None


class Episode(MediuxModel):
    id: int
    number: int = Field(alias="episode_number")
    title: str = Field(alias="episode_title")


class Season(MediuxModel):
    episodes: list[Episode]
    id: Annotated[int | str, BeforeValidator(int_or_str)]
    number: int = Field(alias="season_number")
    title: str | None = Field(alias="season_name", default=None)


class Show(MediuxModel):
    id: int
    release_date: date | None = Field(alias="first_air_date")
    seasons: list[Season]
    title: str


class ShowSet(MediuxModel):
    last_updated: datetime | None = Field(alias="date_updated")
    files: list[File]
    id: int
    set_title: str
    show: Show = Field(alias="show_id")
    username: str = Field(validation_alias=AliasPath("user_created", "username"))


class Movie(MediuxModel):
    id: int
    release_date: date | None
    title: str


class MovieSet(MediuxModel):
    last_updated: datetime | None = Field(alias="date_updated")
    files: list[File]
    id: int
    movie: Movie = Field(alias="movie_id")
    set_title: str
    username: str = Field(validation_alias=AliasPath("user_created", "username"))


class Collection(MediuxModel):
    id: int
    movies: list[Movie]
    title: str = Field(alias="collection_name")


class CollectionSet(MediuxModel):
    collection: Collection = Field(alias="collection_id")
    last_updated: datetime | None = Field(alias="date_updated")
    files: list[File]
    id: int
    set_title: str
    username: str = Field(validation_alias=AliasPath("user_created", "username"))
