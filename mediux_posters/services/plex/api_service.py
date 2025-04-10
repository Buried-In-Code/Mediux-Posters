__all__ = ["Plex"]

import logging
from json import JSONDecodeError
from platform import release, system

from httpx import Client, HTTPStatusError, RequestError, TimeoutException
from pydantic import TypeAdapter, ValidationError
from ratelimit import limits, sleep_and_retry

from mediux_posters import __version__
from mediux_posters.constants import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.services._base import BaseService
from mediux_posters.services.plex.api_schemas import (
    Collection,
    Episode,
    Library,
    MediaType,
    Movie,
    Season,
    Show,
)

LOGGER = logging.getLogger(__name__)
MINUTE = 60


class Plex(BaseService[Show, Season, Episode, Collection, Movie]):
    def __init__(self, base_url: str, token: str):
        self.client = Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "X-Plex-Token": token,
                "User-Agent": f"Mediux-Posters/{__version__}/{system()}: {release()}",
            },
        )

    @classmethod
    def extract_id(cls, entry: dict, prefix: str = "tmdb") -> str | None:
        if "Label" in entry:
            return next(
                iter(
                    x.get("Tag", "").casefold().removeprefix(f"{prefix}-")
                    for x in entry.get("Label", [])
                    if x.get("Tag", "").casefold().startswith(f"{prefix}-")
                ),
                None,
            )
        return next(
            iter(
                x.get("Id", "").removeprefix(f"{prefix}://")
                for x in entry.get("Guid", [])
                if x.get("Id", "").startswith(f"{prefix}://")
            ),
            None,
        )

    @sleep_and_retry
    @limits(calls=30, period=MINUTE)
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
            CONSOLE.print(f"{endpoint=}, {params=}")
            raise ServiceError("Unable to parse response as Json") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err

    @sleep_and_retry
    @limits(calls=30, period=MINUTE)
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

    def _parse_show(self, plex_show: dict) -> Show:
        show = TypeAdapter(Show).validate_python(plex_show)
        for plex_season in self._list_seasons(show_id=show.id):
            season = TypeAdapter(Season).validate_python(plex_season)
            for plex_episode in self._list_episodes(season_id=season.id):
                episode = TypeAdapter(Episode).validate_python(plex_episode)
                season.episodes.append(episode)
            show.seasons.append(season)
        return show

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
                if not tmdb or (tmdb_id is not None and tmdb != tmdb_id):
                    continue
                try:
                    output.append(self._parse_show(plex_show=result))
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def _list_seasons(self, show_id: int) -> list[dict]:
        return (
            self._perform_get_request(
                endpoint=f"/library/metadata/{show_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )

    def _list_episodes(self, season_id: int) -> list[dict]:
        return (
            self._perform_get_request(
                endpoint=f"/library/metadata/{season_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )

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

    def _list_collection_movies(self, collection_id: int) -> list[dict]:
        return (
            self._perform_get_request(
                endpoint=f"/library/metadata/{collection_id}/children", params={"includeGuids": 1}
            )
            .get("MediaContainer", {})
            .get("Metadata", [])
        )

    def _parse_collection(self, plex_collection: dict) -> Collection:
        collection = TypeAdapter(Collection).validate_python(plex_collection)
        collection.movies = [
            self._parse_movie(x) for x in self._list_collection_movies(collection_id=collection.id)
        ]
        return collection

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
                if not tmdb or (tmdb_id is not None and tmdb != tmdb_id):
                    continue
                try:
                    output.append(self._parse_collection(plex_collection=result))
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def list_collections(self, skip_libraries: list[str] | None = None) -> list[Collection]:
        return self._list_collections(skip_libraries=skip_libraries)

    def get_collection(self, tmdb_id: int) -> Collection | None:
        return next(iter(self._list_collections(tmdb_id=tmdb_id)), None)

    def _parse_movie(self, plex_movie: dict) -> Movie:
        return TypeAdapter(Movie).validate_python(plex_movie)

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
                if not tmdb or (tmdb_id is not None and tmdb != tmdb_id):
                    continue
                try:
                    output.append(self._parse_movie(plex_movie=result))
                except ValidationError as err:
                    raise ServiceError(err) from err
        return output

    def list_movies(self, skip_libraries: list[str] | None = None) -> list[Movie]:
        return self._list_movies(skip_libraries=skip_libraries)

    def get_movie(self, tmdb_id: int) -> Movie | None:
        return next(iter(self._list_movies(tmdb_id=tmdb_id)), None)

    def upload_posters(
        self, obj: Show | Season | Episode | Movie | Collection, kometa_integration: bool
    ) -> None:
        pass
