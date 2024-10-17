__all__ = ["Jellyfin"]

import logging
import mimetypes
from base64 import b64encode
from pathlib import Path
from typing import Literal

from requests import get, post
from requests.exceptions import ConnectionError, HTTPError, JSONDecodeError, ReadTimeout

from mediux_posters.console import CONSOLE, create_menu
from mediux_posters.mediux import Collection, Mediux, Movie, Show
from mediux_posters.settings import Jellyfin as JellyfinSettings
from mediux_posters.utils import find_poster

LOGGER = logging.getLogger(__name__)


class Jellyfin:
    def __init__(self, settings: JellyfinSettings, timeout: int = 30):
        self.base_url = settings.base_url
        self.headers = {"X-Emby-Token": settings.api_key}
        self.timeout = timeout

    def _get(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        if params is None:
            params = {}
        if headers is None:
            headers = self.headers
        try:
            response = get(
                f"{self.base_url}{endpoint}", headers=headers, timeout=self.timeout, params=params
            )
            response.raise_for_status()
            return response.json()
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s%s'", self.base_url, endpoint)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except JSONDecodeError:
            LOGGER.error("Unable to parse response from '%s%s' as Json", self.base_url, endpoint)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return {}

    def _post(self, endpoint: str, data: bytes, headers: dict[str, str] | None = None) -> bool:
        if headers is None:
            headers = self.headers
        try:
            response = post(
                f"{self.base_url}{endpoint}", headers=headers, timeout=self.timeout, data=data
            )
            response.raise_for_status()
            return True
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s%s'", self.base_url, endpoint)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except JSONDecodeError:
            LOGGER.error("Unable to parse response from '%s%s' as Json", self.base_url, endpoint)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return False

    def search(
        self, name: str, mediatype: Literal["Series", "Movie", "BoxSet"], year: int | None = None
    ) -> list[dict]:
        response = self._get(
            endpoint="/Search/Hints", params={"searchTerm": name, "includeItemTypes": [mediatype]}
        ).get("SearchHints", [])
        if response and year:
            return [x for x in response if x["ProductionYear"] == year]
        return response

    def list_seasons(self, show_id: str) -> list[tuple[str, int, str]]:
        response = self._get(endpoint=f"/Shows/{show_id}/Seasons").get("Items", [])
        return [(x["Id"], x["IndexNumber"], x["Name"]) for x in response]

    def list_episodes(self, show_id: str, season_id: str) -> list[tuple[str, int, str]]:
        response = self._get(
            endpoint=f"/Shows/{show_id}/Episodes", params={"seasonId": season_id}
        ).get("Items", [])
        return [(x["Id"], x["IndexNumber"], x["Name"]) for x in response]

    def _upload_image(self, id: str, image_type: str, image_path: Path) -> None:  # noqa: A002
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        headers = self.headers
        headers["Content-Type"] = mime_type
        with image_path.open("rb") as stream:
            image_data = b64encode(stream.read())
        if not self._post(
            endpoint=f"/Items/{id}/Images/{image_type}", headers=headers, data=image_data
        ):
            LOGGER.error(
                "[Jellyfin] Failed to upload '%s/%s'", image_path.parent.name, image_path.name
            )

    def _load_poster(
        self,
        mediatype: Literal["shows", "movies", "collections"],
        folder: str,
        filename: str,
        mediux: Mediux,
        poster_id: str,
        image_id: str,
        image_type: Literal["Primary", "Backdrop", "Thumb"],
    ) -> None:
        poster_path = find_poster(mediatype=mediatype, folder=folder, filename=filename)
        if not poster_path.exists():
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            mediux.download_image(id=poster_id, output_file=poster_path)
        if poster_path.exists():
            with CONSOLE.status(
                rf"\[Jellyfin] Uploading {poster_path.parent.name}/{poster_path.name}"
            ):
                self._upload_image(id=image_id, image_type=image_type, image_path=poster_path)

    def lookup_show(self, show: Show, mediux: Mediux) -> None:
        results = self.search(name=show.name, year=show.year, mediatype="Series")
        if not results:
            results = self.search(name=show.name, mediatype="Series")
        if not results:
            LOGGER.warning("[Jellyfin] Unable to find '%s'", show.filename)
            return

        results.sort(key=lambda x: (x["Name"], x["ProductionYear"]))
        index = create_menu(
            options=[f"{x['Name']} ({x['ProductionYear']})" for x in results],
            title=show.filename,
            subtitle="Jellyfin",
            default="None of the Above",
        )
        if index == 0:
            return
        show_result = results[index - 1]
        show_id = show_result["Id"]

        if show.poster_id:
            self._load_poster(
                mediatype="shows",
                folder=show.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=show.poster_id,
                image_id=show_id,
                image_type="Primary",
            )
        if show.backdrop_id:
            self._load_poster(
                mediatype="shows",
                folder=show.filename,
                filename="Backdrop",
                mediux=mediux,
                poster_id=show.backdrop_id,
                image_id=show_id,
                image_type="Backdrop",
            )
        for season_id, season_num, _ in self.list_seasons(show_id=show_id):
            season = next(iter(x for x in show.seasons if x.number == season_num), None)
            if not season:
                continue
            if season.poster_id:
                self._load_poster(
                    mediatype="shows",
                    folder=show.filename,
                    filename=f"Season-{season.number:02d}",
                    mediux=mediux,
                    poster_id=season.poster_id,
                    image_id=season_id,
                    image_type="Primary",
                )
            for episode_id, episode_num, _ in self.list_episodes(
                show_id=show_id, season_id=season_id
            ):
                episode = next(iter(x for x in season.episodes if x.number == episode_num), None)
                if not episode:
                    continue
                if episode.title_card_id:
                    self._load_poster(
                        mediatype="shows",
                        folder=show.filename,
                        filename=f"S{season.number:02d}E{episode.number:02d}",
                        mediux=mediux,
                        poster_id=episode.title_card_id,
                        image_id=episode_id,
                        image_type="Primary",
                    )

    def lookup_movie(self, movie: Movie, mediux: Mediux, folder: str | None = None) -> None:
        results = self.search(name=movie.name, year=movie.year, mediatype="Movie")
        if not results:
            results = self.search(name=movie.name, mediatype="Movie")
        if not results:
            LOGGER.warning("[Jellyfin] Unable to find '%s'", movie.filename)
            return

        results.sort(key=lambda x: (x["Name"], x["ProductionYear"]))
        index = create_menu(
            options=[f"{x['Name']} ({x['ProductionYear']})" for x in results],
            title=movie.filename,
            default="None of the Above",
        )
        if index == 0:
            return
        movie_result = results[index - 1]
        movie_id = movie_result["Id"]

        if movie.poster_id:
            if folder:
                self._load_poster(
                    mediatype="collections",
                    folder=folder,
                    filename=movie.filename,
                    mediux=mediux,
                    poster_id=movie.poster_id,
                    image_id=movie_id,
                    image_type="Primary",
                )
            else:
                self._load_poster(
                    mediatype="movies",
                    folder=movie.filename,
                    filename="Poster",
                    mediux=mediux,
                    poster_id=movie.poster_id,
                    image_id=movie_id,
                    image_type="Primary",
                )

    def lookup_collection(self, collection: Collection, mediux: Mediux) -> None:
        results = self.search(name=collection.name, mediatype="BoxSet")
        if not results:
            LOGGER.warning("[Jellyfin] Unable to find '%s'", collection.name)
            return

        results.sort(key=lambda x: x["Name"])
        index = create_menu(
            options=[x["Name"] for x in results], title=collection.name, default="None of the Above"
        )
        if index == 0:
            return
        collection_result = results[index - 1]
        collection_id = collection_result["Id"]

        if collection.poster_id:
            self._load_poster(
                mediatype="collections",
                folder=collection.name,
                filename="Poster",
                mediux=mediux,
                poster_id=collection.poster_id,
                image_id=collection_id,
                image_type="Primary",
            )
        if collection.backdrop_id:
            self._load_poster(
                mediatype="collections",
                folder=collection.name,
                filename="Backdrop",
                mediux=mediux,
                poster_id=collection.backdrop_id,
                image_id=collection_id,
                image_type="Backdrop",
            )
        for movie in collection.movies:
            self.lookup_movie(movie=movie, mediux=mediux, folder=collection.name)
