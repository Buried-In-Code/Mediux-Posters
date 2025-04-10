__all__ = ["Plex"]

import logging

from plexapi.collection import Collection as PlexCollection
from plexapi.exceptions import BadRequest, NotFound
from plexapi.server import PlexServer
from plexapi.video import Movie as PlexMovie, Show as PlexShow
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout  # noqa: A004

from mediux_posters import get_cache_root
from mediux_posters.constants import CONSOLE
from mediux_posters.services._base import BaseService
from mediux_posters.services.plex.schemas import Collection, Episode, Movie, Season, Show

LOGGER = logging.getLogger(__name__)


class Plex(BaseService[Show, Season, Episode, Collection, Movie]):
    def __init__(self, base_url: str, token: str):
        self.session = PlexServer(base_url, token)

    @classmethod
    def extract_id(
        cls, entry: PlexShow | PlexMovie | PlexCollection, prefix: str = "tmdb"
    ) -> str | None:
        if isinstance(entry, PlexCollection):
            return next(
                iter(
                    x.tag.casefold().removeprefix(f"{prefix}-")
                    for x in entry.labels
                    if x.tag.casefold().startswith(f"{prefix}-")
                ),
                None,
            )
        return next(
            iter(
                x.id.removeprefix(f"{prefix}://")
                for x in entry.guids
                if x.id.startswith(f"{prefix}://")
            ),
            None,
        )

    def _parse_show(self, plex_show: PlexShow) -> Show:
        show = Show(
            id=plex_show.ratingKey,
            imdb_id=self.extract_id(prefix="imdb", entry=plex_show),
            name=plex_show.title,
            premiere_date=plex_show.originallyAvailableAt.date()
            if plex_show.originallyAvailableAt
            else None,
            tmdb_id=self.extract_id(prefix="tmdb", entry=plex_show),
            tvdb_id=self.extract_id(prefix="tvdb", entry=plex_show),
            year=plex_show.year,
            plex=plex_show,
        )
        for plex_season in show.plex.seasons():
            season = Season(
                id=plex_season.ratingKey,
                imdb_id=self.extract_id(prefix="imdb", entry=plex_season),
                name=plex_season.title,
                number=plex_season.index,
                tmdb_id=self.extract_id(prefix="tmdb", entry=plex_season),
                tvdb_id=self.extract_id(prefix="tvdb", entry=plex_season),
                plex=plex_season,
            )
            for plex_episode in season.plex.episodes():
                episode = Episode(
                    id=plex_episode.ratingKey,
                    imdb_id=self.extract_id(prefix="imdb", entry=plex_episode),
                    name=plex_episode.title,
                    number=plex_episode.index,
                    premiere_date=plex_episode.originallyAvailableAt.date()
                    if plex_episode.originallyAvailableAt
                    else None,
                    tmdb_id=self.extract_id(prefix="tmdb", entry=plex_episode),
                    tvdb_id=self.extract_id(prefix="tvdb", entry=plex_episode),
                    plex=plex_episode,
                )
                season.episodes.append(episode)
            show.seasons.append(season)
        return show

    def _list_shows(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Show]:
        skip_libraries = skip_libraries or []
        output = []
        for library in self.session.library.sections():
            if library.type == "show" and library.title not in skip_libraries:
                for show in library.all():
                    tmdb = self.extract_id(entry=show)
                    if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                        continue
                    output.append(self._parse_show(plex_show=show))
        return output

    def list_shows(self, skip_libraries: list[str] | None = None) -> list[Show]:
        return self._list_shows(skip_libraries=skip_libraries)

    def get_show(self, tmdb_id: int) -> Show | None:
        return next(iter(self._list_shows(tmdb_id=tmdb_id)), None)

    def _parse_collection(self, collection: PlexCollection) -> Collection:
        return Collection(
            id=collection.ratingKey,
            name=collection.title,
            tmdb_id=self.extract_id(entry=collection),
            plex=collection,
            movies=[self._parse_movie(movie=x) for x in collection.items()],
        )

    def _list_collections(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Collection]:
        skip_libraries = skip_libraries or []
        output = []
        for library in self.session.library.sections():
            if library.type == "movie" and library.title not in skip_libraries:
                for collection in library.collections():
                    tmdb = self.extract_id(entry=collection)
                    if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                        continue
                    output.append(self._parse_collection(collection=collection))
        return output

    def list_collections(self, skip_libraries: list[str] | None = None) -> list[Collection]:
        return self._list_collections(skip_libraries=skip_libraries)

    def get_collection(self, tmdb_id: int) -> Collection | None:
        return next(iter(self._list_collections(tmdb_id=tmdb_id)), None)

    def _parse_movie(self, movie: PlexMovie) -> Movie:
        return Movie(
            id=movie.ratingKey,
            imdb_id=self.extract_id(prefix="imdb", entry=movie),
            name=movie.title,
            premiere_date=movie.originallyAvailableAt.date(),
            tmdb_id=self.extract_id(prefix="tmdb", entry=movie),
            tvdb_id=self.extract_id(prefix="tvdb", entry=movie),
            year=movie.year,
            plex=movie,
        )

    def _list_movies(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Movie]:
        skip_libraries = skip_libraries or []
        output = []
        for library in self.session.library.sections():
            if library.type == "movie" and library.title not in skip_libraries:
                for movie in library.all():
                    tmdb = self.extract_id(entry=movie)
                    if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                        continue
                    output.append(self._parse_movie(movie=movie))
        return output

    def list_movies(self, skip_libraries: list[str] | None = None) -> list[Movie]:
        return self._list_movies(skip_libraries=skip_libraries)

    def get_movie(self, tmdb_id: int) -> Movie | None:
        return next(iter(self._list_movies(tmdb_id=tmdb_id)), None)

    def upload_posters(
        self, obj: Show | Season | Episode | Movie | Collection, kometa_integration: bool
    ) -> None:
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
            with CONSOLE.status(rf"\[Plex] Uploading {image_file.parent.title}/{image_file.title}"):
                try:
                    func(filepath=str(image_file))
                    setattr(obj, field, True)
                    if kometa_integration:
                        obj.plex.removeLabel("Overlay").reload()
                except (ConnectionError, HTTPError, ReadTimeout, BadRequest, NotFound) as err:
                    LOGGER.error(
                        "[Plex] Failed to upload %s: %s",
                        image_file.relative_to(get_cache_root() / "covers"),
                        err,
                    )
