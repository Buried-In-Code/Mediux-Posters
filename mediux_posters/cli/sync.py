import logging
from argparse import _SubParsersAction

from rich_argparse import HelpPreviewAction, RichHelpFormatter

from mediux_posters.cli.common import (
    ProcessContext,
    ServiceOption,
    filter_sets,
    process_collection_data,
    process_movie_data,
    process_show_data,
    setup_services,
)
from mediux_posters.cli.enum import enum_arg
from mediux_posters.console import CONSOLE
from mediux_posters.errors import ServiceError
from mediux_posters.mediux import CollectionSet, MovieSet, ShowSet
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)


def register(subparsers: _SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "sync",
        help="Synchronize posters by fetching data from Mediux and updating your services",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "-S",
        "--skip-service",
        action="append",
        type=enum_arg(enum_type=ServiceOption),
        choices=list(ServiceOption),
        default=[],
        metavar="SERVICE",
        help=(
            "List of services to skip. "
            "Specify this option multiple times for skipping multiple services."
        ),
    )
    parser.add_argument(
        "-T",
        "--skip-type",
        action="append",
        type=enum_arg(enum_type=MediaType),
        choices=list(MediaType),
        default=[],
        metavar="TYPE",
        help=(
            "List of media types to skip. "
            "Specify this option multiple times for skipping multiple types."
        ),
    )
    parser.add_argument(
        "-L",
        "--skip-library",
        action="append",
        default=[],
        metavar="LIBRARY",
        help=(
            "List of libraries to skip. "
            "Specify this option multiple times for skipping multiple libraries."
        ),
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Pause script to allow user selection of set.",
    )
    parser.add_argument(
        "-s",
        "--start",
        type=int,
        default=0,
        metavar="INDEX",
        help="The starting index for processing media.",
    )
    parser.add_argument(
        "-e",
        "--end",
        type=int,
        default=100_000,
        metavar="INDEX",
        help="The ending index for processing media.",
    )
    parser.add_argument(
        "-c", "--clean", action="store_true", help="Delete the whole cache before starting."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode to show extra logging information for troubleshooting.",
    )
    parser.add_argument(
        "--generate-help-preview", action=HelpPreviewAction, path="docs/img/mediux-posters_sync.svg"
    )
    parser.set_defaults(func=run)


def run(args) -> None:  # noqa: ANN001, C901
    settings, mediux, services = setup_services(
        skip_services=args.skip_service, clean=args.clean, debug=args.debug
    )
    service_count = len(services)
    for service_idx, service in enumerate(services, start=1):
        CONSOLE.rule(
            f"[{service_idx}/{service_count}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        for media_type in MediaType:
            if media_type in args.skip_type:
                continue
            with CONSOLE.status(rf"\[{type(service).__name__}] Fetching {media_type.value} media"):
                try:
                    entries = service.list(media_type=media_type, skip_libraries=args.skip_library)[
                        args.start : args.end
                    ]
                except ServiceError as err:
                    LOGGER.error("[%s] %s", type(service).__name__, err)
                    continue
            ctx = ProcessContext(
                mediux=mediux,
                service=service,
                covers_cache=settings.covers.path,
                priority_usernames=settings.priority_usernames,
                excluded_usernames=settings.exclude_usernames,
                kometa_integration=settings.kometa_integration,
                store_cover=settings.covers.store,
            )
            entry_count = len(entries)
            for idx, entry in enumerate(entries, start=1):
                CONSOLE.print(
                    rf"[{idx}/{entry_count}] {entry.display_name} \[tmdb-{entry.tmdb_id}]"
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
                        interactive=args.interactive,
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
