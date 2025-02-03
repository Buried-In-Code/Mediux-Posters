__all__ = ["Jellyfin"]

import logging
import mimetypes
from base64 import b64encode
from typing import Literal

from requests import get, post
from requests.exceptions import (
    ConnectionError,  # noqa: A004
    HTTPError,
    JSONDecodeError,
    ReadTimeout,
)

from mediux_posters.console import CONSOLE
from mediux_posters.services._base import BaseEpisode, BaseMovie, BaseSeason, BaseService, BaseShow
from mediux_posters.settings import Jellyfin as JellyfinSettings

LOGGER = logging.getLogger(__name__)


class Episode(BaseEpisode):
    pass


class Season(BaseSeason):
    pass


class Show(BaseShow):
    pass


class Movie(BaseMovie):
    pass


class Jellyfin(BaseService[Show, Season, Episode, None, Movie]):
    def __init__(self, settings: JellyfinSettings, timeout: int = 30):
        self.base_url = settings.base_url
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

    def _search(
        self, library_type: Literal["tvshows", "movies"], search_id: int
    ) -> Show | Movie | None:
        libraries = self._get(endpoint="/Library/MediaFolders").get("Items", [])
        libraries = [x for x in libraries if x.get("CollectionType") == library_type]

        for library in libraries:
            for show in self._get(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.get("Id"),
                    "Recursive": True,
                    "IncludeItemTypes": "Series",
                },
            ).get("Items", []):
                tmdb_id = self.extract_tmdb(entry=show)
                if not tmdb_id or tmdb_id != search_id:
                    continue
                return self._parse_show(show_data=show)
            for movie in self._get(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.get("Id"),
                    "Recursive": True,
                    "IncludeItemTypes": "Movie",
                },
            ).get("Items", []):
                tmdb_id = self.extract_tmdb(entry=movie)
                if not tmdb_id or tmdb_id != search_id:
                    continue
                return self._parse_movie(movie=movie)
        return None

    def _parse_show(self, show_data: dict) -> Show:
        show = Show(
            id=show_data["Id"],
            name=show_data["Name"],
            year=show_data["ProductionYear"],
            tmdb_id=self.extract_tmdb(entry=show_data),
        )
        for season_data in self._get(endpoint=f"/Shows/{show.id}/Seasons").get("Items", []):
            season = Season(id=season_data["Id"], number=season_data["IndexNumber"])
            for episode_data in self._get(
                endpoint=f"/Shows/{show.id}/Episodes", params={"seasonId": season.id}
            ).get("Items", []):
                if "IndexNumber" not in episode_data:
                    continue
                episode = Episode(id=episode_data["Id"], number=episode_data["IndexNumber"])
                season.episodes.append(episode)
            show.seasons.append(season)
        return show

    def list_shows(self, skip_libraries: list[str] | None = None) -> list[Show]:
        if skip_libraries is None:
            skip_libraries = []
        libraries = self._get(endpoint="/Library/MediaFolders").get("Items", [])
        libraries = [
            x
            for x in libraries
            if x.get("CollectionType") == "tvshows" and x.get("Name") not in skip_libraries
        ]

        output = []
        for library in libraries:
            for show in self._get(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.get("Id"),
                    "Recursive": True,
                    "IncludeItemTypes": "Series",
                },
            ).get("Items", []):
                tmdb_id = self.extract_tmdb(entry=show)
                if not tmdb_id:
                    continue
                output.append(self._parse_show(show_data=show))
        return output

    def get_show(self, tmdb_id: int) -> Show | None:
        return self._search(library_type="tvshows", search_id=tmdb_id)

    def _parse_movie(self, movie: dict) -> Movie:
        return Movie(
            id=movie["Id"],
            name=movie["Name"],
            year=movie["ProductionYear"],
            tmdb_id=self.extract_tmdb(entry=movie),
        )

    def list_movies(self, skip_libraries: list[str] | None = None) -> list[Movie]:
        if skip_libraries is None:
            skip_libraries = []
        libraries = self._get(endpoint="/Library/MediaFolders").get("Items", [])
        libraries = [
            x
            for x in libraries
            if x.get("CollectionType") == "tvshows" and x.get("Name") not in skip_libraries
        ]

        output = []
        for library in libraries:
            for movie in self._get(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.get("Id"),
                    "Recursive": True,
                    "IncludeItemTypes": "Movie",
                },
            ).get("Items", []):
                tmdb_id = self.extract_tmdb(entry=movie)
                if not tmdb_id:
                    continue
                output.append(self._parse_movie(movie=movie))
        return output

    def get_movie(self, tmdb_id: int) -> Movie | None:
        return self._search(library_type="movies", search_id=tmdb_id)

    def list_collections(self, skip_libraries: list[str] | None = None) -> list:  # noqa: ARG002
        return []

    def get_collection(self, tmdb_id: int) -> None:  # noqa: ARG002
        return None

    def upload_posters(self, obj: Show | Season | Episode | Movie | None) -> None:
        if isinstance(obj, Show | Movie):
            options = [
                (obj.poster, "poster_uploaded", "Primary"),
                (obj.backdrop, "backdrop_uploaded", "Backdrop"),
            ]
        elif isinstance(obj, Season):
            options = [(obj.poster, "poster_uploaded", "Primary")]
        elif isinstance(obj, Episode):
            options = [(obj.title_card, "title_card_uploaded", "Primary")]
        else:
            LOGGER.warning("Updating %s posters aren't supported", type(obj).__name__)
            return
        for image_file, field, image_type in options:
            if not image_file or not image_file.exists() or getattr(obj, field):
                continue
            with CONSOLE.status(
                rf"\[Jellyfin] Uploading {image_file.parent.name}/{image_file.name}"
            ):
                mime_type, _ = mimetypes.guess_type(image_file)
                if not mime_type:
                    mime_type = "image/jpeg"
                headers = self.headers
                headers["Content-Type"] = mime_type
                with image_file.open("rb") as stream:
                    image_data = b64encode(stream.read())
                if not self._post(
                    endpoint=f"/Items/{obj.id}/Images/{image_type}",
                    headers=headers,
                    body=image_data,
                ):
                    LOGGER.error(
                        "[Jellyfin] Failed to upload '%s/%s'",
                        image_file.parent.name,
                        image_file.name,
                    )
                else:
                    setattr(obj, field, True)

    @classmethod
    def extract_tmdb(cls, entry: dict) -> int | None:
        if tmdb_id := entry.get("ProviderIds", {}).get("Tmdb"):
            return int(tmdb_id)
        return None
