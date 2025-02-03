__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection as PlexCollection
from plexapi.exceptions import BadRequest
from plexapi.server import PlexServer
from plexapi.video import (
    Episode as PlexEpisode,
    Movie as PlexMovie,
    Season as PlexSeason,
    Show as PlexShow,
)
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout  # noqa: A004

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.services._base import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseService,
    BaseShow,
)
from mediux_posters.settings import Plex as PlexSettings

LOGGER = logging.getLogger(__name__)


class Episode(BaseEpisode, arbitrary_types_allowed=True):
    plex: PlexEpisode | None = None


class Season(BaseSeason, arbitrary_types_allowed=True):
    plex: PlexSeason | None = None


class Show(BaseShow, arbitrary_types_allowed=True):
    plex: PlexShow | None = None


class Movie(BaseMovie, arbitrary_types_allowed=True):
    plex: PlexMovie | None = None


class Collection(BaseCollection, arbitrary_types_allowed=True):
    plex: PlexCollection | None = None


class Plex(BaseService[Show, Season, Episode, Collection, Movie]):
    def __init__(self, settings: PlexSettings):
        self.session = PlexServer(settings.base_url, settings.token)

    @classmethod
    def extract_tmdb(cls, entry: PlexShow | PlexMovie | PlexCollection) -> int | None:
        if isinstance(entry, PlexCollection):
            return next(
                iter(
                    int(x.tag.casefold().removeprefix("tmdb-"))
                    for x in entry.labels
                    if x.tag.casefold().startswith("tmdb-")
                ),
                None,
            )
        return next(
            iter(
                int(x.id.removeprefix("tmdb://")) for x in entry.guids if x.id.startswith("tmdb://")
            ),
            None,
        )

    def _search(
        self, library_type: Literal["movie", "show", "collection"], search_id: int
    ) -> Show | Movie | Collection | None:
        for library in self.session.library.sections():
            if library.type == "show" and library.type == library_type:
                for show in library.all():
                    tmdb_id = self.extract_tmdb(entry=show)
                    if not tmdb_id or tmdb_id != search_id:
                        continue
                    return self._parse_show(plex_show=show)
            elif library.type == "movie" and library_type in (library.type, "collection"):
                if library_type == "movie":
                    for movie in library.all():
                        tmdb_id = self.extract_tmdb(entry=movie)
                        if not tmdb_id or tmdb_id != search_id:
                            continue
                        return self._parse_movie(movie=movie)
                elif library_type == "collection":
                    for collection in library.collections():
                        tmdb_id = self.extract_tmdb(entry=collection)
                        if not tmdb_id or tmdb_id != search_id:
                            continue
                        return self._parse_collection(collection=collection)
        return None

    def _parse_show(self, plex_show: PlexShow) -> Show:
        show = Show(
            id=plex_show.ratingKey,
            name=plex_show.title,
            year=plex_show.year,
            tmdb_id=self.extract_tmdb(entry=plex_show),
            plex=plex_show,
        )
        for plex_season in show.plex.seasons():
            season = Season(id=plex_season.ratingKey, number=plex_season.index, plex=plex_season)
            for plex_episode in season.plex.episodes():
                episode = Episode(
                    id=plex_episode.ratingKey, number=plex_episode.index, plex=plex_episode
                )
                season.episodes.append(episode)
            show.seasons.append(season)
        return show

    def list_shows(self, skip_libraries: list[str] | None = None) -> list[Show]:
        if skip_libraries is None:
            skip_libraries = []
        output = []
        for library in self.session.library.sections():
            if library.type == "show" and library.title not in skip_libraries:
                for show in library.all():
                    tmdb_id = self.extract_tmdb(entry=show)
                    if not tmdb_id:
                        continue
                    output.append(self._parse_show(plex_show=show))
        return output

    def get_show(self, tmdb_id: int) -> Show | None:
        return self._search(library_type="show", search_id=tmdb_id)

    def _parse_movie(self, movie: PlexMovie) -> Movie:
        return Movie(
            id=movie.ratingKey,
            name=movie.title,
            year=movie.year,
            tmdb_id=self.extract_tmdb(entry=movie),
            plex=movie,
        )

    def list_movies(self, skip_libraries: list[str] | None = None) -> list[Movie]:
        if skip_libraries is None:
            skip_libraries = []
        output = []
        for library in self.session.library.sections():
            if library.type == "movie" and library.title not in skip_libraries:
                for movie in library.all():
                    tmdb_id = self.extract_tmdb(entry=movie)
                    if not tmdb_id:
                        continue
                    output.append(self._parse_movie(movie=movie))
        return output

    def get_movie(self, tmdb_id: int) -> Movie | None:
        return self._search(library_type="movie", search_id=tmdb_id)

    def _parse_collection(self, collection: PlexCollection) -> Collection:
        return Collection(
            id=collection.ratingKey,
            name=collection.title,
            tmdb_id=self.extract_tmdb(entry=collection),
            plex=collection,
        )

    def list_collections(self, skip_libraries: list[str] | None = None) -> list[Collection]:
        if skip_libraries is None:
            skip_libraries = []
        output = []
        for library in self.session.library.sections():
            if library.type == "movie" and library.title not in skip_libraries:
                for collection in library.collections():
                    tmdb_id = self.extract_tmdb(entry=collection)
                    if not tmdb_id:
                        continue
                    output.append(self._parse_collection(collection=collection))
        return output

    def get_collection(self, tmdb_id: int) -> Collection | None:
        return self._search(library_type="collection", search_id=tmdb_id)

    def upload_posters(self, obj: Show | Season | Episode | Movie | Collection) -> None:
        if isinstance(obj, Show | Movie | Collection):
            options = [
                (obj.poster, "poster_uploaded", obj.plex.uploadPoster),
                (obj.backdrop, "backdrop_uploaded", obj.plex.uploadArt),
            ]
        elif isinstance(obj, Season):
            options = [(obj.poster, "poster_uploaded", obj.plex.uploadPoster)]
        elif isinstance(obj, Episode):
            options = [(obj.title_card, "title_card_uploaded", obj.plex.uploadPoster)]
        else:
            LOGGER.warning("Updating %s posters aren't supported", type(obj).__name__)
            return
        for image_file, field, func in options:
            if not image_file or not image_file.exists() or getattr(obj, field):
                continue
            with CONSOLE.status(rf"\[Plex] Uploading {image_file.parent.name}/{image_file.name}"):
                try:
                    func(filepath=str(image_file))
                    setattr(obj, field, True)
                except (ConnectionError, HTTPError, ReadTimeout, BadRequest) as err:
                    LOGGER.error(
                        "[Plex] Failed to upload %s: %s",
                        image_file.relative_to(get_cache_root() / "covers"),
                        err,
                    )
