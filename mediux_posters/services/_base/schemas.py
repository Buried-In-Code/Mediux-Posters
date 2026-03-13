__all__ = ["BaseCollection", "BaseEpisode", "BaseMovie", "BaseSeason", "BaseShow"]


from pydantic import Field

from mediux_posters.utils import BaseModel


class BaseEpisode(BaseModel):
    id: int | str
    number: int

    title_card_uploaded: bool = False
    backdrop_uploaded: bool = False

    @property
    def all_posters_uploaded(self) -> bool:
        return self.title_card_uploaded and self.backdrop_uploaded


class BaseSeason(BaseModel):
    id: int | str
    number: int

    episodes: list[BaseEpisode] = Field(default_factory=list)
    poster_uploaded: bool = False
    backdrop_uploaded: bool = False

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and all(x.all_posters_uploaded for x in self.episodes)
        )


class BaseShow(BaseModel):
    id: int | str
    name: str
    tmdb_id: int
    year: int

    seasons: list[BaseSeason] = Field(default_factory=list)
    poster_uploaded: bool = False
    backdrop_uploaded: bool = False
    logo_uploaded: bool = False
    album_uploaded: bool = False

    @property
    def display_name(self) -> str:
        if self.name.endswith(f"({self.year})"):
            return self.name
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and self.logo_uploaded
            and self.album_uploaded
            and all(x.all_posters_uploaded for x in self.seasons)
        )


class BaseMovie(BaseModel):
    id: str | int
    name: str
    tmdb_id: int
    year: int

    poster_uploaded: bool = False
    backdrop_uploaded: bool = False
    logo_uploaded: bool = False
    album_uploaded: bool = False

    @property
    def display_name(self) -> str:
        if self.name.endswith(f"({self.year})"):
            return self.name
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and self.logo_uploaded
            and self.album_uploaded
        )


class BaseCollection(BaseModel):
    id: str | int
    name: str
    tmdb_id: int

    movies: list[BaseMovie] = Field(default_factory=list)
    poster_uploaded: bool = False
    backdrop_uploaded: bool = False
    logo_uploaded: bool = False
    album_uploaded: bool = False

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def all_posters_uploaded(self) -> bool:
        return (
            self.poster_uploaded
            and self.backdrop_uploaded
            and self.logo_uploaded
            and self.album_uploaded
            and all(x.all_posters_uploaded for x in self.movies)
        )
