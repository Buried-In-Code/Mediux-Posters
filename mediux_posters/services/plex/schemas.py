__all__ = ["Collection", "Episode", "Library", "Movie", "Season", "Show"]

from datetime import date
from enum import Enum

from pydantic import Field, model_validator
from pydantic.alias_generators import to_camel

from mediux_posters.services._base import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)
from mediux_posters.utils import BaseModel


class PlexModel(BaseModel, alias_generator=to_camel, extra="ignore"): ...


class MediaType(str, Enum):
    ARTIST = "artist"
    MOVIE = "movie"
    PHOTO = "photo"
    SHOW = "show"


class Library(PlexModel):
    id: int = Field(alias="key")
    title: str
    type: MediaType


class Episode(BaseEpisode, PlexModel):
    id: int = Field(alias="ratingKey")
    name: str = Field(alias="title")
    number: int = Field(alias="index")
    premiere_date: date | None = Field(alias="originallyAvailableAt", default=None)

    @model_validator(mode="before")
    def extract_guids(cls, data: object) -> object:
        if isinstance(data, dict) and "Guid" in data:
            services = {
                f"{x['id'].split('://')[0]}_id": x["id"].split("://")[1]
                for x in data["Guid"]
                if "id" in x
            }
            data.update(services)
            del data["Guid"]
        return data


class Season(BaseSeason, PlexModel):
    id: int = Field(alias="ratingKey")
    name: str = Field(alias="title")
    number: int = Field(alias="index")

    @model_validator(mode="before")
    def extract_guids(cls, data: object) -> object:
        if isinstance(data, dict) and "Guid" in data:
            services = {
                f"{x['id'].split('://')[0]}_id": x["id"].split("://")[1]
                for x in data["Guid"]
                if "id" in x
            }
            data.update(services)
            del data["Guid"]
        return data


class Show(BaseShow, PlexModel):
    id: int = Field(alias="ratingKey")
    name: str = Field(alias="title")
    premiere_date: date = Field(alias="originallyAvailableAt")

    @model_validator(mode="before")
    def extract_guids(cls, data: object) -> object:
        if isinstance(data, dict) and "Guid" in data:
            services = {
                f"{x['id'].split('://')[0]}_id": x["id"].split("://")[1]
                for x in data["Guid"]
                if "id" in x
            }
            data.update(services)
            del data["Guid"]
        return data


class Movie(BaseMovie, PlexModel):
    id: int = Field(alias="ratingKey")
    name: str = Field(alias="title")
    premiere_date: date = Field(alias="originallyAvailableAt")

    @model_validator(mode="before")
    def extract_guids(cls, data: object) -> object:
        if isinstance(data, dict) and "Guid" in data:
            services = {
                f"{x['id'].split('://')[0]}_id": x["id"].split("://")[1]
                for x in data["Guid"]
                if "id" in x
            }
            data.update(services)
            del data["Guid"]
        return data


class Collection(BaseCollection, PlexModel):
    id: int = Field(alias="ratingKey")
    name: str = Field(alias="title")

    @model_validator(mode="before")
    def extract_guids(cls, data: object) -> object:
        if isinstance(data, dict) and "Label" in data:
            if tag := next(iter(x for x in data["Label"] if x["tag"].startswith("Tmdb-")), {}).get(
                "tag"
            ):
                data["tmdb_id"] = int(tag.removeprefix("Tmdb-"))
            del data["Label"]
        return data
