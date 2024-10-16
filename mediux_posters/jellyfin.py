__all__ = ["Jellyfin"]

import logging
import mimetypes
from base64 import b64encode
from pathlib import Path
from typing import Literal

from requests import get, post
from requests.exceptions import ConnectionError, HTTPError, JSONDecodeError, ReadTimeout

from mediux_posters.console import CONSOLE, create_menu
from mediux_posters.mediux import Collection, Movie, Show
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

    def list_seasons(self, series_id: str) -> list[tuple[str, int, str]]:
        response = self._get(endpoint=f"/Shows/{series_id}/Seasons").get("Items", [])
        return [(x["Id"], x["IndexNumber"], x["Name"]) for x in response]

    def list_episodes(self, series_id: str, season_id: str) -> list[tuple[str, int, str]]:
        response = self._get(
            endpoint=f"/Shows/{series_id}/Episodes", params={"seasonId": season_id}
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

    def update_show(self, show: Show) -> None:
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
            default="None of the Above",
        )
        if index == 0:
            return
        series = results[index - 1]
        series_id = series["Id"]

        with CONSOLE.status(r"\[Jellyfin] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="shows", folder=show.filename, filename="Poster"
            ):
                status.update(rf"\[Jellyfin] Uploading {show.filename} Poster")
                self._upload_image(id=series_id, image_type="Primary", image_path=poster_path)
            if backdrop_path := find_poster(
                mediatype="shows", folder=show.filename, filename="Backdrop"
            ):
                status.update(rf"\[Jellyfin] Uploading {show.filename} Backdrop")
                self._upload_image(id=series_id, image_type="Backdrop", image_path=backdrop_path)
            for season_id, season_num, _ in self.list_seasons(series_id=series_id):
                if season_path := find_poster(
                    mediatype="shows", folder=show.filename, filename=f"Season-{season_num:02d}"
                ):
                    status.update(
                        rf"\[Jellyfin] Uploading {show.filename} S{season_num:02d} Poster"
                    )
                    self._upload_image(id=season_id, image_type="Primary", image_path=season_path)
                for episode_id, episode_num, _ in self.list_episodes(
                    series_id=series_id, season_id=season_id
                ):
                    if episode_path := find_poster(
                        mediatype="shows",
                        folder=show.filename,
                        filename=f"S{season_num:02d}E{episode_num:02d}",
                    ):
                        status.update(
                            rf"\[Jellyfin] Uploading {show.filename} S{season_num:02d}E{episode_num:02d} Title Card"  # noqa: E501
                        )
                        self._upload_image(
                            id=episode_id, image_type="Primary", image_path=episode_path
                        )
                        self._upload_image(
                            id=episode_id, image_type="Thumb", image_path=episode_path
                        )

    def update_movie(self, movie: Movie, folder: str | None = None) -> None:
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

        with CONSOLE.status(r"\[Jellyfin] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="collections" if folder else "movies",
                folder=folder or movie.filename,
                filename=movie.filename if folder else "Poster",
            ):
                status.update(rf"\[Jellyfin] Uploading {movie.filename} Poster")
                self._upload_image(id=movie_id, image_type="Primary", image_path=poster_path)

    def update_collection(self, collection: Collection) -> None:
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

        with CONSOLE.status(r"\[Jellyfin] Uploading ...") as status:
            if poster_path := find_poster(
                mediatype="collections", folder=collection.name, filename="Poster"
            ):
                status.update(rf"\[Jellyfin] Uploading {collection.name} Poster")
                self._upload_image(id=collection_id, image_type="Primary", image_path=poster_path)
            if backdrop_path := find_poster(
                mediatype="collections", folder=collection.name, filename="Backdrop"
            ):
                status.update(rf"\[Jellyfin] Uploading {collection.name} Backdrop")
                self._upload_image(
                    id=collection_id, image_type="Backdrop", image_path=backdrop_path
                )

        for movie in collection.movies:
            self.update_movie(movie=movie, folder=collection.name)
