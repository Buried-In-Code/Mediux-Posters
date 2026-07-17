__all__ = ["register"]

import logging
from argparse import _SubParsersAction

from rich_argparse import HelpPreviewAction, RichHelpFormatter

from mediux_posters.cli.common import (
    ProcessContext,
    ServiceOption,
    process_collection_data,
    process_movie_data,
    process_show_data,
    setup_services,
)
from mediux_posters.cli.enum import enum_arg
from mediux_posters.console import CONSOLE
from mediux_posters.errors import ServiceError
from mediux_posters.mediux import CollectionSet, Mediux, MovieSet, ShowSet
from mediux_posters.utils import MediaType

LOGGER = logging.getLogger(__name__)


def register(subparsers: _SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "set",
        help="Manually set posters for specific Mediux sets using URLs.",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument("urls", nargs="+", help="List of URLs from Mediux to process.")
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
        "-c", "--clean", action="store_true", help="Delete the whole cache before starting."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode to show extra logging information for troubleshooting.",
    )
    parser.add_argument(
        "--generate-help-preview", action=HelpPreviewAction, path="docs/img/mediux-posters_set.svg"
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
        url_count = len(args.urls)
        for idx, url in enumerate(args.urls, start=1):
            if not url.startswith(f"{Mediux.WEB_URL}/sets/"):
                continue
            try:
                set_id = int(url.split("/")[-1])
            except ValueError:
                LOGGER.warning("Unable to parse %s as an int", url.split("/")[-1])
                continue
            with CONSOLE.status(rf"\[Mediux] Searching for Set id: {set_id}"):
                try:
                    set_data: ShowSet | CollectionSet | MovieSet | None = (
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
            ctx = ProcessContext(
                mediux=mediux,
                service=service,
                force=True,
                covers_cache=settings.covers.path,
                priority_usernames=settings.priority_usernames,
                excluded_usernames=settings.exclude_usernames,
                kometa_integration=settings.kometa_integration,
                store_cover=settings.covers.store,
            )
            if media_type is MediaType.SHOW:
                assert isinstance(set_data, ShowSet)  # noqa: S101
                process_show_data(entry=entry, set_data=set_data, ctx=ctx)
            elif media_type is MediaType.COLLECTION:
                assert isinstance(set_data, CollectionSet)  # noqa: S101
                process_collection_data(entry=entry, set_data=set_data, ctx=ctx)
            elif media_type is MediaType.MOVIE:
                assert isinstance(set_data, MovieSet)  # noqa: S101
                process_movie_data(entry=entry, set_data=set_data, ctx=ctx)
