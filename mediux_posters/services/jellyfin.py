__all__ = ["Jellyfin"]

import logging
import mimetypes
from base64 import b64encode
from pathlib import Path
from typing import Literal

from requests import get, post
from requests.exceptions import ConnectionError, HTTPError, JSONDecodeError, ReadTimeout

from mediux_posters.console import CONSOLE
from mediux_posters.mediux import Mediux, Movie as MediuxMovie, Show as MediuxShow
from mediux_posters.settings import Jellyfin as JellyfinSettings
from mediux_posters.utils import find_poster

LOGGER = logging.getLogger(__name__)


class Jellyfin:
    def __init__(self, settings: JellyfinSettings, timeout: int = 30):
        self.base_url = settings.base_url
        self.username = settings.username
        self.headers = {"X-Emby-Token": settings.token}
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
        url = f"{self.base_url}{endpoint}"
        try:
            response = get(url=url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s'", url)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except JSONDecodeError:
            LOGGER.error("Unable to parse response from '%s' as Json", url)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return {}

    def _post(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | dict[str, str] | None = None,
    ) -> bool:
        if params is None:
            params = {}
        if headers is None:
            headers = self.headers
        url = f"{self.base_url}{endpoint}"
        try:
            if isinstance(body, bytes):
                response = post(
                    url=url, headers=headers, params=params, timeout=self.timeout, data=body
                )
            elif isinstance(body, dict):
                response = post(
                    url=url, headers=headers, params=params, timeout=self.timeout, json=body
                )
            else:
                response = post(url=url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            return True
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s'", url)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except JSONDecodeError:
            LOGGER.error("Unable to parse response from '%s' as Json", url)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return False

    def _get_user(self) -> dict:
        return next(
            iter(x for x in self._get(endpoint="/Users") if x.get("Name") == self.username), {}
        )

    def _get_libraries(self) -> list[dict]:
        return self._get(endpoint="/Library/MediaFolders").get("Items", [])

    def _get_items(self, user_id: str, library_id: str) -> list[dict]:
        return self._get(
            endpoint="/Items",
            params={
                "userId": user_id,
                "hasTmdbId": True,
                "parentId": library_id,
                "fields": ["ProviderIds"],
            },
        ).get("Items", [])

    def _list_seasons(self, show_id: str) -> list[tuple[str, int, str]]:
        response = self._get(endpoint=f"/Shows/{show_id}/Seasons").get("Items", [])
        return [(x["Id"], x["IndexNumber"], x["Name"]) for x in response if "Id" in x and "IndexNumber" in x and "Name" in x]

    def _list_episodes(self, show_id: str, season_id: str) -> list[tuple[str, int, str]]:
        response = self._get(
            endpoint=f"/Shows/{show_id}/Episodes", params={"seasonId": season_id}
        ).get("Items", [])
        return [(x["Id"], x["IndexNumber"], x["Name"]) for x in response if "Id" in x and "IndexNumber" in x and "Name" in x]

    def list(self, mediatype: Literal["tvshows", "movies"]) -> list[dict]:
        results = []
        user = self._get_user()
        for library in self._get_libraries():
            if library.get("CollectionType") != mediatype:
                continue
            results.extend(self._get_items(user_id=user.get("Id"), library_id=library.get("Id")))
        return results

    def _upload_image(self, item_id: str, image_type: str, image_path: Path) -> None:
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"
        headers = self.headers
        headers["Content-Type"] = mime_type
        with image_path.open("rb") as stream:
            image_data = b64encode(stream.read())
        if not self._post(
            endpoint=f"/Items/{item_id}/Images/{image_type}", headers=headers, body=image_data
        ):
            LOGGER.error(
                "[Jellyfin] Failed to upload '%s/%s'", image_path.parent.name, image_path.name
            )

    def _upload_poster(
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
                self._upload_image(item_id=image_id, image_type=image_type, image_path=poster_path)

    def upload_show_posters(self, data: MediuxShow, mediux: Mediux, show_id: str) -> None:
        if data.poster_id:
            self._upload_poster(
                mediatype="shows",
                folder=data.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=data.poster_id,
                image_id=show_id,
                image_type="Primary",
            )
        if data.backdrop_id:
            self._upload_poster(
                mediatype="shows",
                folder=data.filename,
                filename="Backdrop",
                mediux=mediux,
                poster_id=data.backdrop_id,
                image_id=show_id,
                image_type="Backdrop",
            )
        for season_id, season_num, _ in self._list_seasons(show_id=show_id):
            mediux_season = next(iter(x for x in data.seasons if x.number == season_num), None)
            if not mediux_season:
                continue
            if mediux_season.poster_id:
                self._upload_poster(
                    mediatype="shows",
                    folder=data.filename,
                    filename=f"Season-{mediux_season.number:02d}",
                    mediux=mediux,
                    poster_id=mediux_season.poster_id,
                    image_id=season_id,
                    image_type="Primary",
                )
            for episode_id, episode_num, _ in self._list_episodes(
                show_id=show_id, season_id=season_id
            ):
                mediux_episode = next(
                    iter(x for x in mediux_season.episodes if x.number == episode_num), None
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
                        image_id=episode_id,
                        image_type="Primary",
                    )

    def upload_movie_posters(self, data: MediuxMovie, mediux: Mediux, movie_id: str) -> None:
        if data.poster_id:
            self._upload_poster(
                mediatype="movies",
                folder=data.filename,
                filename="Poster",
                mediux=mediux,
                poster_id=data.poster_id,
                image_id=movie_id,
                image_type="Primary",
            )
