__all__ = ["Jellyfin"]

import logging
import mimetypes
from base64 import b64encode
from json import JSONDecodeError
from pathlib import Path
from platform import release, system
from typing import Literal

from httpx import Client, HTTPStatusError, RequestError, TimeoutException
from pydantic import TypeAdapter, ValidationError

from mediux_posters import __project__, __version__
from mediux_posters.console import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.services._base import BaseService
from mediux_posters.services.jellyfin.schemas import (
    Collection,
    Episode,
    Library,
    Movie,
    Season,
    Show,
)
from mediux_posters.services.service_cache import ServiceCache

LOGGER = logging.getLogger(__name__)


class Jellyfin(BaseService[Show, Season, Episode, Collection, Movie]):
    def __init__(self, base_url: str, token: str):
        super().__init__(cache=ServiceCache(service="jellyfin"))
        self.client = Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "X-Emby-Token": token,
                "User-Agent": f"{__project__}/{__version__}/{system()}: {release()}",
            },
        )

    @classmethod
    def extract_id(cls, entry: dict, prefix: str = "Tmdb") -> str | None:
        return entry.get("ProviderIds", {}).get(prefix)

    def _perform_get_request(
        self, endpoint: str, params: dict[str, str | list[str]] | None = None
    ) -> dict:
        if params is None:
            params = {}

        try:
            response = self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except RequestError as err:
            raise ServiceError(f"Unable to connect to '{err.request.url.path}'") from err
        except HTTPStatusError as err:
            try:
                error_msg = f"{err.response.json()['title']}: {err.response.json()['detail']}"
                if err.response.status_code in (401, 403):
                    raise AuthenticationError(f"{err.response.status_code}: {error_msg}")
                raise ServiceError(f"{err.response.status_code}: {error_msg}")
            except JSONDecodeError as err:
                raise ServiceError("Unable to parse response as Json") from err
        except JSONDecodeError as err:
            raise ServiceError("Unable to parse response as Json") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err

    def _perform_post_request(
        self, endpoint: str, body: bytes, headers: dict[str, str] | None = None
    ) -> None:
        if headers is None:
            headers = {}

        try:
            response = self.client.post(endpoint, headers=headers, data=body)
            response.raise_for_status()
        except RequestError as err:
            raise ServiceError(f"Unable to connect to '{err.request.url.path}'") from err
        except HTTPStatusError as err:
            try:
                error_msg = f"{err.response.json()['title']}: {err.response.json()['detail']}"
                if err.response.status_code in (401, 403):
                    raise AuthenticationError(f"{err.response.status_code}: {error_msg}")
                raise ServiceError(f"{err.response.status_code}: {error_msg}")
            except JSONDecodeError as err:
                raise ServiceError("Unable to parse response as Json") from err
        except JSONDecodeError as err:
            raise ServiceError("Unable to parse response as Json") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err

    def _list_libraries(
        self,
        media_type: Literal["movies", "tvshows", "unknown"],
        skip_libraries: list[str] | None = None,
    ) -> list[Library]:
        skip_libraries = skip_libraries or []
        results = [
            x
            for x in self._perform_get_request(endpoint="/Library/MediaFolders").get("Items", [])
            if x.get("CollectionType") == media_type
        ]
        results = [x for x in results if x.get("Name") not in skip_libraries]
        try:
            return TypeAdapter(list[Library]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def validate(self) -> bool:
        try:
            self._list_libraries(media_type="movies")
            return True
        except ServiceError as err:
            LOGGER.warning("[Jellyfin] %s", err)
        return False

    def list_episodes(self, show_id: str, season_id: str) -> list[Episode]:
        results = self._perform_get_request(
            endpoint=f"/Shows/{show_id}/Episodes",
            params={"seasonId": season_id, "fields": ["ProviderIds"]},
        ).get("Items", [])
        return TypeAdapter(list[Episode]).validate_python(results)

    def list_seasons(self, show_id: str) -> list[Season]:
        results = self._perform_get_request(
            endpoint=f"/Shows/{show_id}/Seasons", params={"fields": ["ProviderIds"]}
        ).get("Items", [])
        return TypeAdapter(list[Season]).validate_python(results)

    def _list_shows(
        self,
        skip_libraries: list[str] | None = None,
        tmdb_id: int | None = None,
        series_id: str | None = None,
    ) -> list[Show]:
        libraries = self._list_libraries(media_type="tvshows", skip_libraries=skip_libraries)
        output = []
        for library in libraries:
            results = self._perform_get_request(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.id,
                    "Recursive": True,
                    "IncludeItemTypes": "Series",
                    "Ids": [series_id],
                },
            ).get("Items", [])
            for result in results:
                tmdb = self.extract_id(entry=result)
                if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                    continue
                try:
                    result = TypeAdapter(Show).validate_python(result)
                    output.append(result)
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def list_shows(self, skip_libraries: list[str] | None = None) -> list[Show]:
        return self._list_shows(skip_libraries=skip_libraries)

    def get_show(self, tmdb_id: int) -> Show | None:
        return next(iter(self._list_shows(tmdb_id=tmdb_id)), None)

    def list_collections(self, skip_libraries: list[str] | None = None) -> list[Collection]:  # noqa: ARG002
        return []

    def get_collection(self, tmdb_id: int) -> Collection | None:  # noqa: ARG002
        return None

    def list_collection_movies(self, collection_id: int | str) -> list[Movie]:  # noqa: ARG002
        return []

    def _list_movies(
        self,
        skip_libraries: list[str] | None = None,
        tmdb_id: int | None = None,
        movie_id: str | None = None,
    ) -> list[Movie]:
        libraries = self._list_libraries(media_type="movies", skip_libraries=skip_libraries)
        output = []
        for library in libraries:
            results = self._perform_get_request(
                endpoint="/Items",
                params={
                    "hasTmdbId": True,
                    "fields": ["ProviderIds"],
                    "ParentId": library.id,
                    "Recursive": True,
                    "IncludeItemTypes": "Movie",
                    "Ids": [movie_id],
                },
            ).get("Items", [])
            for result in results:
                tmdb = self.extract_id(entry=result)
                if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                    continue
                try:
                    result = TypeAdapter(Movie).validate_python(result)
                    output.append(result)
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def list_movies(self, skip_libraries: list[str] | None = None) -> list[Movie]:
        return self._list_movies(skip_libraries=skip_libraries)

    def get_movie(self, tmdb_id: int) -> Movie | None:
        return next(iter(self._list_movies(tmdb_id=tmdb_id)), None)

    def upload_image(
        self,
        object_id: int | str,
        image_file: Path,
        kometa_integration: bool,  # noqa: ARG002
    ) -> bool:
        with CONSOLE.status(rf"\[Jellyfin] Uploading {image_file.parent.name}/{image_file.name}"):
            image_type = "Backdrop" if image_file.stem == "backdrop" else "Primary"
            mime_type, _ = mimetypes.guess_type(image_file)
            if not mime_type:
                mime_type = "image/jpeg"
            headers = {"Content-Type": mime_type}
            with image_file.open("rb") as stream:
                image_data = b64encode(stream.read())
            try:
                self._perform_post_request(
                    endpoint=f"/Items/{object_id}/Images/{image_type}",
                    headers=headers,
                    body=image_data,
                )
                return True
            except ServiceError as err:
                LOGGER.error(
                    "[Jellyfin] Failed to upload '%s/%s': %s",
                    image_file.parent.name,
                    image_file.name,
                    err,
                )
        return False
