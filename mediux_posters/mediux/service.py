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

from mediux_posters import __version__
from mediux_posters.constants import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.mediux.schemas import CollectionSet, MovieSet, ShowSet

LOGGER = logging.getLogger(__name__)
MINUTE = 60


class Mediux:
    WEB_URL: ClassVar[str] = "https://mediux.pro"

    def __init__(self, base_url: str, api_key: str):
        self.client = Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"Mediux-Posters/{__version__}/{system()}: {release()}",
            },
        )

    @sleep_and_retry
    @limits(calls=30, period=MINUTE)
    def _perform_graphql_request(self, query: str) -> dict[str, Any]:
        try:
            response = self.client.post("/graphql", json={"query": query})
            response.raise_for_status()
            return response.json()
        except RequestError as err:
            raise ServiceError(f"Unable to connect to '{err.request.url.path}'") from err
        except HTTPStatusError as err:
            try:
                error_msg = next((x["message"] for x in err.response.json()["errors"]), None)
                if err.response.status_code in (401, 403):
                    raise AuthenticationError(f"{err.response.status_code}: {error_msg}")
                raise ServiceError(f"{err.response.status_code}: {error_msg}")
            except JSONDecodeError as err:
                raise ServiceError("Unable to parse response as Json") from err
        except JSONDecodeError as err:
            raise ServiceError("Unable to parse response as Json") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err

    def list_show_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[ShowSet]:
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
            fields=[
                "date_created",
                "date_updated",
                Field(
                    name="files",
                    fields=[
                        "id",
                        "file_type",
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
                        "date_updated",
                        "first_air_date",
                        "id",
                        Field(
                            name="seasons",
                            fields=[
                                "date_updated",
                                Field(
                                    name="episodes",
                                    fields=[
                                        "date_updated",
                                        "episode_number",
                                        "episode_title",
                                        "id",
                                    ],
                                ),
                                "id",
                                "season_name",
                                "season_number",
                            ],
                        ),
                        "title",
                    ],
                ),
                Field(name="user_created", fields=["username"]),
            ],
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
            fields=[
                "date_created",
                "date_updated",
                Field(
                    name="files",
                    fields=[
                        "id",
                        "file_type",
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
                        "date_updated",
                        "first_air_date",
                        "id",
                        Field(
                            name="seasons",
                            fields=[
                                "date_updated",
                                Field(
                                    name="episodes",
                                    fields=[
                                        "date_updated",
                                        "episode_number",
                                        "episode_title",
                                        "id",
                                    ],
                                ),
                                "id",
                                "season_name",
                                "season_number",
                            ],
                        ),
                        "title",
                    ],
                ),
                Field(name="user_created", fields=["username"]),
            ],
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
            fields=[
                "date_created",
                "date_updated",
                Field(
                    name="files",
                    fields=[
                        "id",
                        "file_type",
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
                        "date_updated",
                        "id",
                        Field(
                            name="movies", fields=["date_updated", "id", "release_date", "title"]
                        ),
                    ],
                ),
                Field(name="user_created", fields=["username"]),
            ],
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
            fields=[
                "date_created",
                "date_updated",
                "description",
                Field(
                    name="files",
                    fields=[
                        "id",
                        "file_type",
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
                        "date_updated",
                        "id",
                        Field(
                            name="movies",
                            fields=["date_updated", "id", "release_date", "status", "title"],
                        ),
                    ],
                ),
                Field(name="user_created", fields=["username"]),
            ],
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
            fields=[
                "date_created",
                "date_updated",
                "description",
                Field(name="files", fields=["id", "file_type", Field(name="movie", fields=["id"])]),
                "id",
                Field(
                    name="movie_id",
                    fields=["date_updated", "id", "release_date", "status", "title"],
                ),
                "set_title",
                Field(name="user_created", fields=["username"]),
            ],
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
            fields=[
                "date_created",
                "date_updated",
                "description",
                Field(name="files", fields=["id", "file_type", Field(name="movie", fields=["id"])]),
                "id",
                Field(
                    name="movie_id",
                    fields=["date_updated", "id", "release_date", "status", "title"],
                ),
                "set_title",
                Field(name="user_created", fields=["username"]),
            ],
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

    def download_image(self, image_id: str, output: Path) -> None:
        with self.client.stream("GET", f"/assets/{image_id}") as response:
            total = int(response.headers["Content-Length"])

            with Progress(console=CONSOLE) as progress:
                download_task = progress.add_task(f"Downloading {output}", total=total)
                with output.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
                        progress.update(download_task, completed=response.num_bytes_downloaded)
