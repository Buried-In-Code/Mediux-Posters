import logging
from typing import Annotated

from typer import Option

from mediux_posters.cli._typer import app
from mediux_posters.cli.common import (
    ServiceOption,
    filter_sets,
    process_collection_data,
    process_movie_data,
    process_show_data,
    setup_services,
)
from mediux_posters.console import CONSOLE
from mediux_posters.errors import ServiceError
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)


@app.command(
    name="sync", help="Synchronize posters by fetching data from Mediux and updating your services"
)
def sync_posters(
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
    skip_media_types: Annotated[
        list[MediaType],
        Option(
            "--skip-type",
            "-T",
            show_default=False,
            case_sensitive=False,
            default_factory=list,
            help="List of MediaTypes to skip. "
            "Specify this option multiple times for skipping multiple types.",
        ),
    ],
    skip_libraries: Annotated[
        list[str],
        Option(
            "--skip-library",
            "-L",
            show_default=False,
            default_factory=list,
            help="List of libraries to skip. "
            "Specify this option multiple times for skipping multiple libraries.",
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
    start: Annotated[
        int, Option("--start", "-s", help="The starting index for processing media.")
    ] = 0,
    end: Annotated[
        int, Option("--end", "-e", help="The ending index for processing media.")
    ] = 100_000,
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
        for media_type in MediaType:
            if media_type in skip_media_types:
                continue
            with CONSOLE.status(rf"\[{type(service).__name__}] Fetching {media_type.value} media"):
                try:
                    entries = service.list(media_type=media_type, skip_libraries=skip_libraries)[
                        start:end
                    ]
                except ServiceError as err:
                    LOGGER.error("[%s] %s", type(service).__name__, err)
                    continue
            entry_count = len(entries)
            for idx, entry in enumerate(entries, start=1):
                CONSOLE.rule(
                    rf"[{idx}/{entry_count}] {entry.display_name} \[tmdb-{entry.tmdb_id}]",
                    align="left",
                    style="subtitle",
                )
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
                for set_data in filtered_sets:
                    if media_type is MediaType.SHOW:
                        process_show_data(
                            entry=entry,
                            set_data=set_data,
                            mediux=mediux,
                            service=service,
                            priority_usernames=settings.priority_usernames,
                            kometa_integration=settings.kometa_integration,
                        )
                    elif media_type is MediaType.COLLECTION:
                        process_collection_data(
                            entry=entry,
                            set_data=set_data,
                            mediux=mediux,
                            service=service,
                            priority_usernames=settings.priority_usernames,
                            kometa_integration=settings.kometa_integration,
                        )
                    elif media_type is MediaType.MOVIE:
                        process_movie_data(
                            entry=entry,
                            set_data=set_data,
                            mediux=mediux,
                            service=service,
                            priority_usernames=settings.priority_usernames,
                            kometa_integration=settings.kometa_integration,
                        )
                    if entry.all_posters_uploaded:
                        break
