__all__ = ["Collection", "Episode", "Movie", "Season", "Show"]


from plexapi.collection import Collection as PlexCollection
from plexapi.video import (
    Episode as PlexEpisode,
    Movie as PlexMovie,
    Season as PlexSeason,
    Show as PlexShow,
)
from pydantic import Field

from mediux_posters.services._base import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)


class Episode(BaseEpisode, arbitrary_types_allowed=True):
    plex: PlexEpisode | None = None


class Season(BaseSeason, arbitrary_types_allowed=True):
    plex: PlexSeason | None = None


class Show(BaseShow, arbitrary_types_allowed=True):
    plex: PlexShow | None = None


class Movie(BaseMovie, arbitrary_types_allowed=True):
    plex: PlexMovie | None = None


class Collection(BaseCollection, arbitrary_types_allowed=True):
    movies: list[Movie] = Field(default_factory=list)
    plex: PlexCollection | None = None
