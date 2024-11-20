__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.new.mediux import (
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

    def list(
        self, mediatype: Literal["show", "movie", "collection"]
    ) -> list[Show, Movie, Collection]:
        results = []
        try:
            libraries = [
                lib
                for lib in self.session.library.sections()
                if lib.type == ("movie" if mediatype == "collection" else mediatype)
            ]
            for library in libraries:
                if mediatype == "collection":
                    results.extend(library.collections())
                else:
                    results.extend(library.all())
        except ConnectionError:
            LOGGER.error("Unable to connect to Plex Server")
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return results

    def _upload_poster(
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

    def upload_show_posters(self, data: MediuxShow, mediux: Mediux, show: Show) -> None:
        if data.poster_id:
            self._upload_poster(
                mediatype="shows",
                folder=data.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=data.poster_id,
                obj=show,
                image_type="Poster",
            )
        if data.backdrop_id:
            self._upload_poster(
                mediatype="shows",
                folder=data.filename,
                filename="Backdrop",
                mediux=mediux,
                poster_id=data.backdrop_id,
                obj=show,
                image_type="Art",
            )
        for season in show.seasons():
            mediux_season = next(iter([x for x in data.seasons if x.number == season.index]), None)
            if not mediux_season:
                continue
            if mediux_season.poster_id:
                self._upload_poster(
                    mediatype="shows",
                    folder=data.filename,
                    filename=f"Season-{mediux_season.number:02d}",
                    mediux=mediux,
                    poster_id=mediux_season.poster_id,
                    obj=season,
                    image_type="Poster",
                )
            for episode in season.episodes():
                mediux_episode = next(
                    iter([x for x in mediux_season.episodes if x.number == episode.index]), None
                )
                if not mediux_episode:
                    continue
                if mediux_episode.title_card_id:
                    self._upload_poster(
                        mediatype="shows",
                        folder=data.filename,
                        filename=f"S{mediux_season.number:02d}E{mediux_episode.number:02d}",
                        mediux=mediux,
                        poster_id=mediux_episode.title_card_id,
                        obj=episode,
                        image_type="Poster",
                    )

    def upload_movie_posters(self, data: MediuxMovie, mediux: Mediux, movie: Movie) -> None:
        if data.poster_id:
            self._upload_poster(
                mediatype="movies",
                folder=data.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=data.poster_id,
                obj=movie,
                image_type="Poster",
            )

    def upload_collection_posters(
        self, data: MediuxCollection, mediux: Mediux, collection: Collection
    ) -> None:
        if data.poster_id:
            self._upload_poster(
                mediatype="collections",
                folder=data.name,
                filename="Poster",
                mediux=mediux,
                poster_id=data.poster_id,
                obj=collection,
                image_type="Poster",
            )
        if data.backdrop_id:
            self._upload_poster(
                mediatype="collections",
                folder=data.name,
                filename="Backdrop",
                mediux=mediux,
                poster_id=data.backdrop_id,
                obj=collection,
                image_type="Art",
            )

    def search(self, tmdb_id: str) -> Show | Movie | Collection | None:
        for library in [x for x in self.session.library.sections() if x.type in ("movie", "show")]:
            try:
                return library.getGuid(f"tmdb://{tmdb_id}")
            except NotFound:
                continue
        for entry in self.list(mediatype="collection"):
            collection_id = next(
                iter(
                    x.tag.lower().removeprefix("tmdb-")
                    for x in entry.labels
                    if x.tag.lower().startswith("tmdb-")
                ),
                None,
            )
            if tmdb_id == collection_id:
                return entry
        return None
