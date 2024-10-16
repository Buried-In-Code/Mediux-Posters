__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout

from mediux_posters.console import CONSOLE, create_menu
from mediux_posters.mediux import (
    Collection as MediuxCollection,
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

    def update_show(self, show: MediuxShow) -> None:
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
            default="None of the Above",
        )
        if index == 0:
            return
        series = results[index - 1]

        with CONSOLE.status(r"\[Plex] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="shows", folder=show.filename, filename="Poster"
            ):
                status.update(rf"\[Plex] Uploading {show.filename} Poster")
                try:
                    series.uploadPoster(filepath=str(poster_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error("[Plex] Failed to upload %s poster: %s", show.filename, err)
            if backdrop_path := find_poster(
                mediatype="shows", folder=show.filename, filename="Backdrop"
            ):
                status.update(rf"\[Plex] Uploading {show.filename} Backdrop")
                try:
                    series.uploadArt(filepath=str(backdrop_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error("[Plex] Failed to upload %s backdrop: %s", show.filename, err)
            for season in series.seasons():
                if season_path := find_poster(
                    mediatype="shows", folder=show.filename, filename=f"Season-{season.index:02d}"
                ):
                    status.update(rf"\[Plex] Uploading {show.filename} S{season.index:02d} Poster")
                    try:
                        season.uploadPoster(filepath=str(season_path))
                    except (ConnectionError, HTTPError, ReadTimeout) as err:
                        LOGGER.error(
                            "[Plex] Failed to upload %s S%02d poster: %s",
                            show.filename,
                            season.index,
                            err,
                        )
                for episode in season.episodes():
                    if episode_path := find_poster(
                        mediatype="shows",
                        folder=show.filename,
                        filename=f"S{season.index:02d}E{episode.index:02d}",
                    ):
                        status.update(
                            rf"\[Plex] Uploading {show.filename} S{season.index:02d}E{episode.index:02d} Title Card"  # noqa: E501
                        )
                        try:
                            episode.uploadPoster(filepath=str(episode_path))
                        except (ConnectionError, HTTPError, ReadTimeout) as err:
                            LOGGER.error(
                                "[Plex] Failed to upload %s S%02dE%02d title card: %s",
                                show.filename,
                                season.index,
                                episode.index,
                                err,
                            )

    def update_movie(self, movie: MediuxMovie, folder: str | None = None) -> None:
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

        with CONSOLE.status(r"\[Plex] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="collections" if folder else "movies",
                folder=folder or movie.filename,
                filename=movie.filename if folder else "Poster",
            ):
                status.update(rf"\[Plex] Uploading {movie.filename} Poster")
                try:
                    movie_result.uploadPoster(filepath=str(poster_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error("[Plex] Failed to upload %s poster: %s", movie.filename, err)

    def update_collection(self, collection: MediuxCollection) -> None:
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

        with CONSOLE.status(r"\[Plex] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="collections", folder=collection.name, filename="Poster"
            ):
                status.update(rf"\[Plex] Uploading {collection.name} Poster")
                try:
                    collection_result.uploadPoster(filepath=str(poster_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error("[Plex] Failed to upload %s poster: %s", collection.name, err)
            if backdrop_path := find_poster(
                mediatype="collections", folder=collection.name, filename="Backdrop"
            ):
                status.update(rf"\[Plex] Uploading {collection.name} Backdrop")
                try:
                    collection_result.uploadArt(filepath=str(backdrop_path))
                except (ConnectionError, HTTPError, ReadTimeout) as err:
                    LOGGER.error("[Plex] Failed to upload %s backdrop: %s", collection.name, err)

        for movie in collection.movies:
            self.update_movie(movie=movie, folder=collection.name)
