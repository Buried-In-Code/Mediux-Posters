__all__ = ["Plex"]

import logging
from typing import Literal

from plexapi.collection import Collection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.mediux import Mediux
from mediux_posters.settings import Plex as PlexSettings
from mediux_posters.utils import find_poster

LOGGER = logging.getLogger(__name__)


class Plex:
    def __init__(self, settings: PlexSettings):
        self.session = PlexServer(settings.base_url, settings.token)

    def list(self, mediatype: Literal["show", "movie"]) -> list[Show, Movie]:
        results = []
        try:
            libraries = [lib for lib in self.session.library.sections() if lib.type == mediatype]
            for library in libraries:
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

    def upload_show
