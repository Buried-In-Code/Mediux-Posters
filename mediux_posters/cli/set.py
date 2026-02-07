__all__ = ["set_posters"]

import logging
from typing import Annotated

from typer import Argument, Option

from mediux_posters.cli._typer import app
from mediux_posters.cli.common import (
    ServiceOption,
    process_collection_data,
    process_movie_data,
    process_show_data,
    setup_services,
)
from mediux_posters.console import CONSOLE
from mediux_posters.errors import ServiceError
from mediux_posters.mediux import CollectionSet, Mediux, MovieSet, ShowSet
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)


@app.command(name="set", help="Manually set posters for specific Mediux sets using URLs.")
def set_posters(
    urls: Annotated[
        list[str], Argument(show_default=False, help="List of URLs from Mediux to process.")
    ],
    skip_services: Annotated[
        list[ServiceOption],
        Option(
            "--skip-service",
            "-S",
            show_default=False,
            case_sensitive=False,
            default_factory=list,
            help="List of Services to skip. "
            "Specify this option multiple times for skipping multiple services.",
        ),
    ],
    clean: Annotated[
        bool,
        Option("--clean", "-c", show_default=False, help="Delete the whole cache before starting."),
    ] = False,
    debug: Annotated[
        bool,
        Option(
            "--debug",
            help="Enable debug mode to show extra logging information for troubleshooting.",
        ),
    ] = False,
) -> None:
    settings, mediux, services = setup_services(
        skip_services=skip_services, clean=clean, debug=debug
    )
    service_count = len(services)
    for service_idx, service in enumerate(services, start=1):
        CONSOLE.rule(
            f"[{service_idx}/{service_count}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        url_count = len(urls)
        for idx, url in enumerate(urls, start=1):
            if not url.startswith(f"{Mediux.WEB_URL}/sets/"):
                continue
            try:
                set_id = int(url.split("/")[-1])
            except ValueError:
                LOGGER.warning("Unable to parse %s as an int", url.split("/")[-1])
                continue
            with CONSOLE.status(rf"\[Mediux] Searching for Set id: {set_id}"):
                try:
                    set_data = (
                        mediux.get_show_set(set_id=set_id)
                        or mediux.get_collection_set(set_id=set_id)
                        or mediux.get_movie_set(set_id=set_id)
                    )
                    if not set_data:
                        LOGGER.warning("[Mediux] Unable to find set with id: %d", set_id)
                        continue
                except ServiceError as err:
                    LOGGER.error("[Mediux] %s", err)
                    continue
                media_type, tmdb_id = (
                    (MediaType.SHOW, set_data.show.id)
                    if isinstance(set_data, ShowSet)
                    else (MediaType.COLLECTION, set_data.collection.id)
                    if isinstance(set_data, CollectionSet)
                    else (MediaType.MOVIE, set_data.movie.id)
                    if isinstance(set_data, MovieSet)
                    else (None, None)
                )
                if not media_type or not tmdb_id:
                    LOGGER.warning("[Mediux] Unable to determine media type for set id: %d", set_id)
                    continue
            CONSOLE.print(rf"[{idx}/{url_count}] {set_data.set_title} \[tmdb-{tmdb_id}]")
            with CONSOLE.status(rf"\[{type(service).__name__}] Searching for TMDB id: {tmdb_id}"):
                try:
                    entry = service.get(media_type=media_type, tmdb_id=tmdb_id)
                    if not entry:
                        LOGGER.warning(
                            "[%s] Unable to find media with tmdb id: %d",
                            type(service).__name__,
                            tmdb_id,
                        )
                        continue
                except ServiceError as err:
                    LOGGER.error("[%s] %s", type(service).__name__, err)
                    continue
            if media_type is MediaType.SHOW:
                process_show_data(
                    entry=entry,
                    set_data=set_data,
                    mediux=mediux,
                    service=service,
                    force=True,
                    priority_usernames=settings.priority_usernames,
                    kometa_integration=settings.kometa_integration,
                )
            elif media_type is MediaType.COLLECTION:
                process_collection_data(
                    entry=entry,
                    set_data=set_data,
                    mediux=mediux,
                    service=service,
                    force=True,
                    priority_usernames=settings.priority_usernames,
                    kometa_integration=settings.kometa_integration,
                )
            elif media_type is MediaType.MOVIE:
                process_movie_data(
                    entry=entry,
                    set_data=set_data,
                    mediux=mediux,
                    service=service,
                    force=True,
                    priority_usernames=settings.priority_usernames,
                    kometa_integration=settings.kometa_integration,
                )
