__all__ = ["Mediux"]

import logging
import platform
from pathlib import Path
from typing import ClassVar

from gql import Client
from gql.dsl import DSLField, DSLQuery, DSLSchema, dsl_gql
from gql.transport.exceptions import TransportQueryError
from gql.transport.httpx import HTTPXTransport
from httpx import RequestError, TimeoutException, stream
from pydantic import TypeAdapter, ValidationError
from rich.progress import Progress

from mediux_posters import __version__
from mediux_posters.console import CONSOLE
from mediux_posters.errors import AuthenticationError, ServiceError
from mediux_posters.mediux.schemas import CollectionSet, MovieSet, ShowSet
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)


class Mediux:
    WEB_URL: ClassVar[str] = "https://mediux.pro"

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        transport = HTTPXTransport(
            url=self.base_url + "/graphql",
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": f"Mediux-Posters/{__version__} ({platform.system()}: {platform.release()}; Python v{platform.python_version()})",  # noqa: E501
            },
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
        with self.client:
            assert self.client.schema is not None  # noqa: S101
            self.schema = DSLSchema(self.client.schema)

    def validate(self) -> bool:
        try:
            results = self.list_movie_sets(tmdb_id=324857)
            return results != []
        except ServiceError as err:
            LOGGER.error("[Mediux] %s", err)
        return False

    def _directus_files_fields(self) -> list[DSLField]:
        return [
            self.schema.directus_files.id,
            self.schema.directus_files.file_type,
            self.schema.directus_files.modified_on,
            self.schema.directus_files.show.select(self.schema.shows.id),
            self.schema.directus_files.season.select(self.schema.seasons.id),
            self.schema.directus_files.episode.select(self.schema.episodes.id),
            self.schema.directus_files.collection.select(self.schema.collections.id),
            self.schema.directus_files.movie.select(self.schema.movies.id),
        ]

    def _directus_users_fields(self) -> list[DSLField]:
        return [self.schema.directus_users.username]

    def _shows_fields(self) -> list[DSLField]:
        return [
            self.schema.shows.id,
            self.schema.shows.first_air_date,
            self.schema.shows.title,
            self.schema.shows.seasons.select(
                self.schema.seasons.id,
                self.schema.seasons.season_name,
                self.schema.seasons.season_number,
                self.schema.seasons.episodes.select(
                    self.schema.episodes.id,
                    self.schema.episodes.episode_number,
                    self.schema.episodes.episode_title,
                ),
            ),
        ]

    def _show_sets_fields(self) -> list[DSLField]:
        return [
            self.schema.show_sets.id,
            self.schema.show_sets.date_updated,
            self.schema.show_sets.set_title,
            self.schema.show_sets.files.select(*self._directus_files_fields()),
            self.schema.show_sets.show_id.select(*self._shows_fields()),
            self.schema.show_sets.user_created.select(*self._directus_users_fields()),
        ]

    def list_show_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[ShowSet]:
        exclude_usernames = exclude_usernames or []
        filters: dict[str, dict] = {"show_id": {"id": {"_eq": tmdb_id}}}
        if exclude_usernames:
            filters["user_created"] = {"username": {"_nin": exclude_usernames}}
        query = DSLQuery(
            self.schema.Query.show_sets.args(filter=filters).select(*self._show_sets_fields())
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(list[ShowSet]).validate_python(result.get("show_sets", []))
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

    def get_show_set(self, set_id: int) -> ShowSet | None:
        query = DSLQuery(
            self.schema.Query.show_sets_by_id.args(id=set_id).select(*self._show_sets_fields())
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(ShowSet).validate_python(result.get("show_sets_by_id"))
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

    def _collections_fields(self) -> list[DSLField]:
        return [
            self.schema.collections.id,
            self.schema.collections.collection_name,
            self.schema.collections.movies.select(*self._movies_fields()),
        ]

    def _collection_sets_fields(self) -> list[DSLField]:
        return [
            self.schema.collection_sets.id,
            self.schema.collection_sets.date_updated,
            self.schema.collection_sets.set_title,
            self.schema.collection_sets.files.select(*self._directus_files_fields()),
            self.schema.collection_sets.collection_id.select(*self._collections_fields()),
            self.schema.collection_sets.user_created.select(*self._directus_users_fields()),
        ]

    def list_collection_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[CollectionSet]:
        exclude_usernames = exclude_usernames or []
        filters: dict[str, dict] = {"collection_id": {"id": {"_eq": tmdb_id}}}
        if exclude_usernames:
            filters["user_created"] = {"username": {"_nin": exclude_usernames}}
        query = DSLQuery(
            self.schema.Query.collection_sets.args(filter=filters).select(
                *self._collection_sets_fields()
            )
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(list[CollectionSet]).validate_python(
                    result.get("collection_sets", [])
                )
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

    def get_collection_set(self, set_id: int) -> CollectionSet | None:
        query = DSLQuery(
            self.schema.Query.collection_sets_by_id.args(id=set_id).select(
                *self._collection_sets_fields()
            )
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(CollectionSet).validate_python(
                    result.get("collection_sets_by_id")
                )
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

    def _movies_fields(self) -> list[DSLField]:
        return [self.schema.movies.id, self.schema.movies.release_date, self.schema.movies.title]

    def _movie_sets_fields(self) -> list[DSLField]:
        return [
            self.schema.movie_sets.id,
            self.schema.movie_sets.date_updated,
            self.schema.movie_sets.set_title,
            self.schema.movie_sets.files.select(*self._directus_files_fields()),
            self.schema.movie_sets.movie_id.select(*self._movies_fields()),
            self.schema.movie_sets.user_created.select(*self._directus_users_fields()),
        ]

    def list_movie_sets(
        self, tmdb_id: int, exclude_usernames: list[str] | None = None
    ) -> list[MovieSet]:
        exclude_usernames = exclude_usernames or []
        filters: dict[str, dict] = {"movie_id": {"id": {"_eq": tmdb_id}}}
        if exclude_usernames:
            filters["user_created"] = {"username": {"_nin": exclude_usernames}}
        query = DSLQuery(
            self.schema.Query.movie_sets.args(filter=filters).select(*self._movie_sets_fields())
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(list[MovieSet]).validate_python(result.get("movie_sets", []))
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

    def get_movie_set(self, set_id: int) -> MovieSet | None:
        query = DSLQuery(
            self.schema.Query.movie_sets_by_id.args(id=set_id).select(*self._movie_sets_fields())
        )
        with self.client as session:
            try:
                result = session.execute(dsl_gql(query))
                return TypeAdapter(MovieSet).validate_python(result.get("movie_sets_by_id"))
            except TransportQueryError as err:
                raise ServiceError from err
            except ValidationError as err:
                raise ServiceError from err

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

    def download_image(self, file_id: str, output: Path, parent_str: str) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        try:
            with stream(
                method="GET",
                url=f"{self.base_url}/assets/{file_id}",
                headers={"Authorization": f"Bearer {self.token}"},
            ) as response:
                if not response.is_success:
                    if response.status_code in (401, 403):
                        raise AuthenticationError(
                            f"{response.status_code}: {response.reason_phrase}"
                        )
                    raise ServiceError(f"{response.status_code}: {response.reason_phrase}")
                total = int(response.headers.get("Content-Length", 0))

                with Progress(console=CONSOLE, expand=True) as progress:
                    download_task = progress.add_task(
                        f"Downloading {parent_str}/{output.name}", total=total
                    )
                    with output.open("wb") as file_stream:
                        for chunk in response.iter_bytes():
                            file_stream.write(chunk)
                            progress.update(download_task, completed=response.num_bytes_downloaded)
        except RequestError as err:
            raise ServiceError(f"Unable to connect to '{err.request.url.path}'") from err
        except TimeoutException as err:
            raise ServiceError("Service took too long to respond") from err
