__all__ = ["Plex"]

import logging
import mimetypes
from json import JSONDecodeError
from pathlib import Path
from platform import release, system

from httpx import Client, HTTPStatusError, RequestError, TimeoutException
from pydantic import TypeAdapter, ValidationError

from mediux_posters import __project__, __version__
from mediux_posters.console import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.services._base import BaseService
from mediux_posters.services.plex.schemas import (
    Collection,
    Episode,
    Library,
    MediaType,
    Movie,
    Season,
    Show,
)
from mediux_posters.services.service_cache import ServiceCache

LOGGER = logging.getLogger(__name__)


class Plex(BaseService[Show, Season, Episode, Collection, Movie]):
    def __init__(self, base_url: str, token: str):
        super().__init__(cache=ServiceCache(service="plex"))
        self.client = Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "X-Plex-Token": token,
                "User-Agent": f"{__project__}/{__version__}/{system()}: {release()}",
            },
        )

    @classmethod
    def extract_id(cls, entry: dict, prefix: str = "tmdb") -> str | None:
        if "Label" in entry:
            return next(
                iter(
                    x.get("tag", "").casefold().removeprefix(f"{prefix}-")
                    for x in entry.get("Label", [])
                    if x.get("tag", "").casefold().startswith(f"{prefix}-")
                ),
                None,
            )
        return next(
            iter(
                x.get("id", "").removeprefix(f"{prefix}://")
                for x in entry.get("Guid", [])
                if x.get("id", "").startswith(f"{prefix}://")
            ),
            None,
        )

    def _perform_get_request(
        self, endpoint: str, params: dict[str, int | str] | None = None
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

    def _perform_put_request(
        self, endpoint: str, params: dict[str, int | str] | None = None
    ) -> None:
        if params is None:
            params = {}

        try:
            response = self.client.put(endpoint, params=params)
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
        self, media_type: MediaType, skip_libraries: list[str] | None = None
    ) -> list[Library]:
        skip_libraries = skip_libraries or []
        results = [
            x
            for x in self._perform_get_request(endpoint="/library/sections")
            .get("MediaContainer", {})
            .get("Directory", [])
            if x.get("type") == media_type.value
        ]
        results = [x for x in results if x.get("title") not in skip_libraries]
        try:
            return TypeAdapter(list[Library]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def validate(self) -> bool:
        try:
            self._list_libraries(media_type=MediaType.MOVIE)
            return True
        except ServiceError as err:
            LOGGER.warning("[Plex] %s", err)
        return False

    def list_episodes(self, show_id: int, season_id: int) -> list[Episode]:  # noqa: ARG002
        results = (
            self._perform_get_request(
                endpoint=f"/library/metadata/{season_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )
        try:
            return TypeAdapter(list[Episode]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def list_seasons(self, show_id: int) -> list[Season]:
        results = (
            self._perform_get_request(
                endpoint=f"/library/metadata/{show_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )
        try:
            return TypeAdapter(list[Season]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def _list_shows(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Show]:
        libraries = self._list_libraries(media_type=MediaType.SHOW, skip_libraries=skip_libraries)
        output = []
        for library in libraries:
            results = (
                self._perform_get_request(
                    endpoint=f"/library/sections/{library.id}/all", params={"includeGuids": 1}
                )
                .get("MediaContainer", {})
                .get("Metadata", [])
            )
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

    def _get_collection_by_id(self, collection_id: int) -> dict | None:
        return next(
            iter(
                self._perform_get_request(
                    endpoint=f"/library/metadata/{collection_id}", params={"includeGuids": 1}
                )
                .get("MediaContainer", {})
                .get("Metadata", [])
            ),
            None,
        )

    def _list_collections(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Collection]:
        libraries = self._list_libraries(media_type=MediaType.MOVIE, skip_libraries=skip_libraries)
        output = []
        for library in libraries:
            results = [
                self._get_collection_by_id(collection_id=x.get("ratingKey"))
                for x in (
                    self._perform_get_request(
                        endpoint=f"/library/sections/{library.id}/collections",
                        params={"includeGuids": 1},
                    )
                    .get("MediaContainer", {})
                    .get("Metadata", [])
                )
            ]
            for result in results:
                tmdb = self.extract_id(entry=result)
                if not tmdb or (tmdb_id is not None and int(tmdb) != tmdb_id):
                    continue
                try:
                    result = TypeAdapter(Collection).validate_python(result)
                    output.append(result)
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def list_collections(self, skip_libraries: list[str] | None = None) -> list[Collection]:
        return self._list_collections(skip_libraries=skip_libraries)

    def get_collection(self, tmdb_id: int) -> Collection | None:
        return next(iter(self._list_collections(tmdb_id=tmdb_id)), None)

    def list_collection_movies(self, collection_id: int) -> list[Movie]:
        results = (
            self._perform_get_request(
                endpoint=f"/library/metadata/{collection_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )
        try:
            return TypeAdapter(list[Movie]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def _list_movies(
        self, skip_libraries: list[str] | None = None, tmdb_id: int | None = None
    ) -> list[Movie]:
        libraries = self._list_libraries(media_type=MediaType.MOVIE, skip_libraries=skip_libraries)
        output = []
        for library in libraries:
            results = (
                self._perform_get_request(
                    endpoint=f"/library/sections/{library.id}/all", params={"includeGuids": 1}
                )
                .get("MediaContainer", {})
                .get("Metadata", [])
            )
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

    def remove_labels(self, object_id: int | str, *labels: str) -> None:
        self._perform_put_request(
            endpoint=f"/library/metadata/{object_id}", params={"label[].tag.tag-": ",".join(labels)}
        )

    def upload_image(
        self, object_id: int | str, image_file: Path, kometa_integration: bool
    ) -> bool:
        with CONSOLE.status(rf"\[Plex] Uploading {image_file.parent.name}/{image_file.name}"):
            mime_type, _ = mimetypes.guess_type(image_file)
            if not mime_type:
                mime_type = "image/jpeg"
            headers = {"Content-Type": mime_type}
            try:
                with image_file.open("rb") as stream:
                    if image_file.stem == "backdrop":
                        self._perform_post_request(
                            endpoint=f"/library/metadata/{object_id}/arts",
                            headers=headers,
                            body=stream.read(),
                        )
                    else:
                        self._perform_post_request(
                            endpoint=f"/library/metadata/{object_id}/posters",
                            headers=headers,
                            body=stream.read(),
                        )
                    if kometa_integration:
                        self.remove_label("Overlay", object_id=object_id)
                return True
            except ServiceError as err:
                LOGGER.error(
                    "[Plex] Failed to upload '%s/%s': %s",
                    image_file.parent.name,
                    image_file.name,
                    err,
                )
        return False
