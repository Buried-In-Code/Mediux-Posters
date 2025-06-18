__all__ = ["Mediux"]

import logging
from json import JSONDecodeError
from pathlib import Path
from platform import release, system
from typing import Any, ClassVar

from graphql_query import Argument, Field, Operation, Query
from httpx import Client, HTTPStatusError, RequestError, TimeoutException
from pydantic import TypeAdapter, ValidationError
from ratelimit import limits, sleep_and_retry
from rich.progress import Progress

from mediux_posters import __project__, __version__
from mediux_posters.console import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.mediux.schemas import CollectionSet, MovieSet, ShowSet
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)
# 60 Calls per Minute
CALLS = 60
PERIOD = 60


class Mediux:
    WEB_URL: ClassVar[str] = "https://mediux.pro"
    SHOW_FIELDS: ClassVar[list[str | Field]] = [
        "date_updated",
        Field(
            name="files",
            fields=[
                "id",
                "file_type",
                "modified_on",
                Field(name="show", fields=["id"]),
                Field(name="season", fields=["id"]),
                Field(name="episode", fields=["id"]),
            ],
        ),
        "id",
        "set_title",
        Field(
            name="show_id",
            fields=[
                "first_air_date",
                "id",
                Field(
                    name="seasons",
                    fields=[
                        Field(name="episodes", fields=["episode_number", "episode_title", "id"]),
                        "id",
                        "season_name",
                        "season_number",
                    ],
                ),
                "title",
            ],
        ),
        Field(name="user_created", fields=["username"]),
    ]
    COLLECTION_FIELDS: ClassVar[list[str | Field]] = [
        "date_updated",
        Field(
            name="files",
            fields=[
                "id",
                "file_type",
                "modified_on",
                Field(name="movie", fields=["id"]),
                Field(name="collection", fields=["id"]),
            ],
        ),
        "id",
        "set_title",
        Field(
            name="collection_id",
            fields=[
                "collection_name",
                "id",
                Field(name="movies", fields=["id", "release_date", "title"]),
            ],
        ),
        Field(name="user_created", fields=["username"]),
    ]
    MOVIE_FIELDS: ClassVar[list[str | Field]] = [
        "date_updated",
        Field(
            name="files",
            fields=["id", "file_type", "modified_on", Field(name="movie", fields=["id"])],
        ),
        "id",
        Field(name="movie_id", fields=["id", "release_date", "title"]),
        "set_title",
        Field(name="user_created", fields=["username"]),
    ]

    def __init__(self, base_url: str, token: str):
        self.client = Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": f"{__project__.title()}/{__version__}/{system()}: {release()}",
            },
        )

    @sleep_and_retry
    @limits(calls=CALLS, period=PERIOD)
    def _perform_graphql_request(self, query: str) -> dict[str, Any]:
        try:
            response = self.client.post("/graphql", json={"query": query})
            response.raise_for_status()
            return response.json()
        except RequestError as err:
            raise ServiceError(f"Unable to connect to '{err.request.url.path}'") from err
        except HTTPStatusError as err:
            try:
                errors = err.response.json()["errors"]
                if err.response.status_code in (401, 403):
                    raise AuthenticationError(f"{err.response.status_code}: {errors}")
                raise ServiceError(f"{err.response.status_code}: {errors}")
            except JSONDecodeError as err:
                raise ServiceError("Unable to parse response as Json") from err
        except JSONDecodeError as err:
            raise ServiceError("Unable to parse response as Json") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err

    def validate(self) -> bool:
        try:
            results = self.list_movie_sets(tmdb_id=324857)
            return results != []
        except ServiceError as err:
            LOGGER.error("[Mediux] %s", err)
        return False

    def list_show_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[ShowSet]:
        exclude_usernames = exclude_usernames or []
        filters = [
            Argument(
                name="show_id",
                value=Argument(name="id", value=Argument(name="_eq", value=f'"{tmdb_id}"')),
            )
        ]
        if exclude_usernames:
            filters.append(
                Argument(
                    name="user_created",
                    value=Argument(
                        name="username", value=Argument(name="_nin", value=exclude_usernames)
                    ),
                )
            )
        query = Query(
            name="show_sets",
            arguments=[Argument(name="filter", value=filters)],
            fields=self.SHOW_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            results = (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("show_sets", [])
            )
            return TypeAdapter(list[ShowSet]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def get_show_set(self, set_id: int) -> ShowSet | None:
        query = Query(
            name="show_sets_by_id",
            arguments=[Argument(name="id", value=set_id)],
            fields=self.SHOW_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            if result := (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("show_sets_by_id")
            ):
                return TypeAdapter(ShowSet).validate_python(result)
        except ValidationError as err:
            raise ServiceError(err) from err
        return None

    def list_collection_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[CollectionSet]:
        exclude_usernames = exclude_usernames or []
        filters = [
            Argument(
                name="collection_id",
                value=Argument(name="id", value=Argument(name="_eq", value=f'"{tmdb_id}"')),
            )
        ]
        if exclude_usernames:
            filters.append(
                Argument(
                    name="user_created",
                    value=Argument(
                        name="username", value=Argument(name="_nin", value=exclude_usernames)
                    ),
                )
            )
        query = Query(
            name="collection_sets",
            arguments=[Argument(name="filter", value=filters)],
            fields=self.COLLECTION_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            results = (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("collection_sets", [])
            )
            return TypeAdapter(list[CollectionSet]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def get_collection_set(self, set_id: int) -> CollectionSet | None:
        query = Query(
            name="collection_sets_by_id",
            arguments=[Argument(name="id", value=set_id)],
            fields=self.COLLECTION_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            if result := (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("collection_sets_by_id")
            ):
                return TypeAdapter(CollectionSet).validate_python(result)
        except ValidationError as err:
            raise ServiceError(err) from err
        return None

    def list_movie_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[MovieSet]:
        exclude_usernames = exclude_usernames or []
        filters = [
            Argument(
                name="movie_id",
                value=Argument(name="id", value=Argument(name="_eq", value=f'"{tmdb_id}"')),
            )
        ]
        if exclude_usernames:
            filters.append(
                Argument(
                    name="user_created",
                    value=Argument(
                        name="username", value=Argument(name="_nin", value=exclude_usernames)
                    ),
                )
            )
        query = Query(
            name="movie_sets",
            arguments=[Argument(name="filter", value=filters)],
            fields=self.MOVIE_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            results = (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("movie_sets", [])
            )
            return TypeAdapter(list[MovieSet]).validate_python(results)
        except ValidationError as err:
            raise ServiceError(err) from err

    def get_movie_set(self, set_id: int) -> MovieSet | None:
        query = Query(
            name="movie_sets_by_id",
            arguments=[Argument(name="id", value=set_id)],
            fields=self.MOVIE_FIELDS,
        )
        operation = Operation(type="query", queries=[query])

        try:
            if result := (
                self._perform_graphql_request(query=operation.render())
                .get("data", {})
                .get("movie_sets_by_id")
            ):
                return TypeAdapter(MovieSet).validate_python(result)
        except ValidationError as err:
            raise ServiceError(err) from err
        return None

    def list_sets(
        self, media_type: MediaType, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[ShowSet] | list[CollectionSet] | list[MovieSet]:
        return (
            self.list_show_sets(tmdb_id=tmdb_id, exclude_usernames=exclude_usernames)
            if media_type is MediaType.SHOW
            else self.list_collection_sets(tmdb_id=tmdb_id, exclude_usernames=exclude_usernames)
            if media_type is MediaType.COLLECTION
            else self.list_movie_sets(tmdb_id=tmdb_id, exclude_usernames=exclude_usernames)
            if media_type is MediaType.MOVIE
            else []
        )

    def get_set(
        self, media_type: MediaType, set_id: int
    ) -> ShowSet | CollectionSet | MovieSet | None:
        return (
            self.get_show_set(set_id=set_id)
            if media_type is MediaType.SHOW
            else self.get_collection_set(set_id=set_id)
            if media_type is MediaType.COLLECTION
            else self.get_movie_set(set_id=set_id)
            if media_type is MediaType.MOVIE
            else None
        )

    @sleep_and_retry
    @limits(calls=CALLS, period=PERIOD)
    def download_image(self, file_id: str, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        with self.client.stream("GET", f"/assets/{file_id}") as response:
            total = int(response.headers["Content-Length"])

            with Progress(console=CONSOLE, expand=True) as progress:
                download_task = progress.add_task(
                    f"Downloading {output.parent.name}/{output.name}", total=total
                )
                with output.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
                        progress.update(download_task, completed=response.num_bytes_downloaded)
