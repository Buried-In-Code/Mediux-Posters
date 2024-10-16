__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE, create_menu
from mediux_posters.mediux import (
    Collection as MediuxCollection,
    Mediux,
    Movie as MediuxMovie,
    Show as MediuxShow,
)
from mediux_posters.settings import Plex as PlexSettings
from mediux_posters.utils import find_poster

LOGGER = logging.getLogger(__name__)


class Plex:
    def __init__(self, settings: PlexSettings):
        self.session = PlexServer(settings.base_url, settings.token)

    def search(
        self, name: str, mediatype: Literal["show", "movie", "collection"], year: int | None = None
    ) -> list[Show]:
        results = []
        try:
            results = self.session.search(name, mediatype=mediatype)
        except ConnectionError:
            LOGGER.error("Unable to connect to Plex Server")
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        mediatype = Show if mediatype == "show" else Movie if mediatype == "movie" else Collection
        if results:
            results = [x for x in results if isinstance(x, mediatype)]
            if year:
                return [x for x in results if x.year == year]
            return results
        return []

    def _load_poster(
        self,
        mediatype: Literal["shows", "movies", "collections"],
        folder: str,
        filename: str,
        mediux: Mediux,
        poster_id: str,
        obj: Show | Movie | Collection,
        image_type: Literal["Poster", "Art"],
    ) -> None:
        poster_path = find_poster(mediatype=mediatype, folder=folder, filename=filename)
        if not poster_path.exists():
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            mediux.download_image(id=poster_id, output_file=poster_path)
        if poster_path.exists():
            with CONSOLE.status(rf"\[Plex] Uploading {poster_path.parent.name}/{poster_path.name}"):
                try:
                    if image_type == "Poster":
                        obj.uploadPoster(filepath=str(poster_path))
                    elif image_type == "Art":
                        obj.uploadArt(filepath=str(poster_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error(
                        "[Plex] Failed to upload %s poster: %s",
                        poster_path.relative_to(get_cache_root() / "covers"),
                        err,
                    )

    def lookup_show(self, show: MediuxShow, mediux: Mediux) -> None:
        results = self.search(name=show.name, year=show.year, mediatype="show")
        if not results:
            results = self.search(name=show.name, mediatype="show")
        if not results:
            LOGGER.warning("[Plex] Unable to find '%s'", show.filename)
            return

        results.sort(key=lambda x: (x.title, x.year))
        index = create_menu(
            options=[f"{x.title} ({x.year})" for x in results],
            title=show.filename,
            subtitle="Plex",
            default="None of the Above",
        )
        if index == 0:
            return
        show_result = results[index - 1]

        if show.poster_id:
            self._load_poster(
                mediatype="shows",
                folder=show.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=show.poster_id,
                obj=show_result,
                image_type="Poster",
            )
        if show.backdrop_id:
            self._load_poster(
                mediatype="shows",
                folder=show.filename,
                filename="Backdrop",
                mediux=mediux,
                poster_id=show.backdrop_id,
                obj=show_result,
                image_type="Art",
            )
        for season_result in show_result.seasons():
            season = next(iter([x for x in show.seasons if x.number == season_result.index]), None)
            if not season:
                continue
            if season.poster_id:
                self._load_poster(
                    mediatype="shows",
                    folder=show.filename,
                    filename=f"Season-{season.number:02d}",
                    mediux=mediux,
                    poster_id=season.poster_id,
                    obj=season_result,
                    image_type="Poster",
                )
            for episode_result in season_result.episodes():
                episode = next(
                    iter([x for x in season.episodes if x.number == episode_result.index]), None
                )
                if not episode:
                    continue
                if episode.title_card_id:
                    self._load_poster(
                        mediatype="shows",
                        folder=show.filename,
                        filename=f"S{season.number:02d}E{episode.number:02d}",
                        mediux=mediux,
                        poster_id=episode.title_card_id,
                        obj=episode_result,
                        image_type="Poster",
                    )

    def lookup_movie(self, movie: MediuxMovie, mediux: Mediux, folder: str | None = None) -> None:
        results = self.search(name=movie.name, year=movie.year, mediatype="movie")
        if not results:
            results = self.search(name=movie.name, mediatype="movie")
        if not results:
            LOGGER.warning("[Plex] Unable to find '%s'", movie.filename)
            return

        results.sort(key=lambda x: (x.title, x.year))
        index = create_menu(
            options=[f"{x.title} ({x.year})" for x in results],
            title=movie.filename,
            default="None of the Above",
        )
        if index == 0:
            return
        movie_result = results[index - 1]

        if movie.poster_id:
            if folder:
                self._load_poster(
                    mediatype="collections",
                    folder=folder,
                    filename=movie.filename,
                    mediux=mediux,
                    poster_id=movie.poster_id,
                    obj=movie_result,
                    image_type="Poster",
                )
            else:
                self._load_poster(
                    mediatype="movies",
                    folder=movie.filename,
                    filename="Poster",
                    mediux=mediux,
                    poster_id=movie.poster_id,
                    obj=movie_result,
                    image_type="Poster",
                )

    def lookup_collection(self, collection: MediuxCollection, mediux: Mediux) -> None:
        results = self.search(name=collection.name, mediatype="collection")
        if not results:
            LOGGER.warning("[Plex] Unable to find '%s'", collection.name)
            return

        results.sort(key=lambda x: x.title)
        index = create_menu(
            options=[x.title for x in results], title=collection.name, default="None of the Above"
        )
        if index == 0:
            return
        collection_result = results[index - 1]

        if collection.poster_id:
            self._load_poster(
                mediatype="collections",
                folder=collection.name,
                filename="Poster",
                mediux=mediux,
                poster_id=collection.poster_id,
                obj=collection_result,
                image_type="Poster",
            )
        if collection.backdrop_id:
            self._load_poster(
                mediatype="collections",
                folder=collection.name,
                filename="Backdrop",
                mediux=mediux,
                poster_id=collection.backdrop_id,
                obj=collection_result,
                image_type="Art",
            )
        for movie in collection.movies:
            self.lookup_movie(movie=movie, mediux=mediux, folder=collection.name)
