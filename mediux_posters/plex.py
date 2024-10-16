__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show

from mediux_posters.mediux import Show as MediuxShow
from mediux_posters.settings import Plex as PlexSettings
from mediux_posters.utils import create_menu, find_poster

LOGGER = logging.getLogger(__name__)


class Plex:
    def __init__(self, settings: PlexSettings):
        self.session = PlexServer(settings.base_url, settings.token)

    def search(
        self, name: str, mediatype: Literal["show", "movie", "collection"], year: int | None = None
    ) -> list[Show]:
        results = self.session.search(name, mediatype=mediatype)
        mediatype = Show if mediatype == "show" else Movie if mediatype == "movie" else Collection
        if results:
            results = [x for x in results if isinstance(x, mediatype)]
            if year:
                return [x for x in results if x.year == year]
            return results
        return []

    def update_series_set(self, show: MediuxShow) -> None:
        LOGGER.info("Searching for '%s (%d)' in Plex", show.name, show.year)
        results = self.search(name=show.name, year=show.year, mediatype="show")
        if not results:
            results = self.search(name=show.name, mediatype="show")
        if not results:
            LOGGER.warning("Unable to find '%s (%d)' in Plex", show.name, show.year)
            return

        results.sort(key=lambda x: (x.title, x.year))
        index = create_menu(
            options=[f"{x.title} ({x.year})" for x in results],
            title="Select Series",
            default="None of the Above",
        )
        if index == 0:
            return
        series = results[index - 1]

        if poster_path := find_poster(mediatype="show", folder=show.filename, filename="Poster"):
            LOGGER.info("Updating Poster in Plex")
            series.uploadPoster(filepath=str(poster_path))
        if backdrop_path := find_poster(
            mediatype="show", folder=show.filename, filename="Backdrop"
        ):
            LOGGER.info("Updating Backdrop in Plex")
            series.uploadArt(filepath=str(backdrop_path))
        for season in series.seasons():
            if season_path := find_poster(
                mediatype="show", folder=show.filename, filename=f"Season-{season.index:02d}"
            ):
                LOGGER.info("Updating Season %02d Poster in Plex", season.index)
                season.uploadPoster(filepath=str(season_path))
            for episode in season.episodes():
                if episode_path := find_poster(
                    mediatype="show",
                    folder=show.filename,
                    filename=f"S{season.index:02d}E{episode.index:02d}",
                ):
                    LOGGER.info("Updating Episode %02d Poster in Plex", episode.index)
                    episode.uploadPoster(filepath=str(episode_path))

    def update_collection(self, folder_name: str, collection_name: str) -> None:
        LOGGER.info("Searching for '%s' in Plex", collection_name)
        results = self.search(name=collection_name, mediatype="collection")
        if not results:
            LOGGER.warning("Unable to find '%s' in Plex", collection_name)
            return

        results.sort(key=lambda x: x.title)
        index = create_menu(
            options=[x.title for x in results],
            title="Select Collection",
            default="None of the Above",
        )
        if index == 0:
            return
        collection = results[index - 1]

        if poster_path := find_poster(mediatype="movie", folder=folder_name, filename="Poster"):
            LOGGER.info("Updating '%s' Poster in Plex", collection_name)
            collection.uploadPoster(filepath=str(poster_path))
        if backdrop_path := find_poster(mediatype="movie", folder=folder_name, filename="Backdrop"):
            LOGGER.info("Updating '%s' Backdrop in Plex", collection_name)
            collection.uploadArt(filepath=str(backdrop_path))

    def update_movie(self, folder_name: str, movie: Movie) -> None:
        LOGGER.info("Searching for '%s (%d)' in Plex", movie.name, movie.year)
        results = self.search(name=movie.name, year=movie.year, mediatype="movie")
        if not results:
            results = self.search(name=movie.name, mediatype="movie")
        if not results:
            LOGGER.warning("Unable to find '%s (%d)' in Plex", movie.name, movie.year)
            return

        results.sort(key=lambda x: (x.title, x.year))
        index = create_menu(
            options=[f"{x.title} ({x.year})" for x in results],
            title="Select Movie",
            default="None of the Above",
        )
        if index == 0:
            return
        movie_result = results[index - 1]

        if poster_path := find_poster(
            mediatype="movie", folder=folder_name, filename=movie.filename
        ):
            LOGGER.info("Updating '%s (%d)' Poster in Plex", movie.name, movie.year)
            movie_result.uploadPoster(filepath=str(poster_path))
