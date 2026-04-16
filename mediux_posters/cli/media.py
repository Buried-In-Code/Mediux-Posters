__all__ = ["media_posters"]

import logging
from typing import Annotated

from typer import Argument, Option

from mediux_posters.cli._typer import app
from mediux_posters.cli.common import (
    ProcessContext,
    ServiceOption,
    filter_sets,
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


@app.command(name="media", help="Manually set posters for specific Mediux media using URLs.")
def media_posters(  # noqa: C901
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
    interactive: Annotated[
        bool,
        Option(
            "--interactive",
            "-i",
            show_default=False,
            help="Pause script to allow user selection of set.",
        ),
    ] = False,
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
            media_type = next(
                (x for x in MediaType if url.startswith(f"{Mediux.WEB_URL}/{x}s/")), None
            )
            if not media_type:
                LOGGER.warning("Unknown Mediux url: '%s'", url)
                continue
            try:
                tmdb_id = int(url.split("/")[-1])
            except ValueError:
                LOGGER.warning("Unable to parse %s as an int", url.split("/")[-1])
                continue
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
            CONSOLE.print(rf"[{idx}/{url_count}] {entry.display_name} \[tmdb-{tmdb_id}]")
            with CONSOLE.status(r"\[Mediux] Searching for new Sets"):
                try:
                    set_list = mediux.list_sets(
                        media_type=media_type,
                        tmdb_id=entry.tmdb_id,
                        exclude_usernames=settings.exclude_usernames,
                    )
                except ServiceError as err:
                    LOGGER.error("[Mediux] %s", err)
                    set_list = []
                filtered_sets = filter_sets(
                    set_list=set_list,
                    priority_usernames=settings.priority_usernames,
                    only_priority_usernames=settings.only_priority_usernames,
                    interactive=interactive,
                )
            ctx = ProcessContext(
                mediux=mediux,
                service=service,
                covers_cache=settings.covers.path,
                priority_usernames=settings.priority_usernames,
                excluded_usernames=settings.exclude_usernames,
                kometa_integration=settings.kometa_integration,
                covers_store=settings.covers.store,
            )
            for set_data in filtered_sets:
                if media_type is MediaType.SHOW:
                    set_data: ShowSet
                    process_show_data(entry=entry, set_data=set_data, ctx=ctx)
                elif media_type is MediaType.COLLECTION:
                    set_data: CollectionSet
                    process_collection_data(entry=entry, set_data=set_data, ctx=ctx)
                elif media_type is MediaType.MOVIE:
                    set_data: MovieSet
                    process_movie_data(entry=entry, set_data=set_data, ctx=ctx)
                if entry.all_posters_uploaded:
                    break
