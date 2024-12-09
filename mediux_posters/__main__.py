import json
import logging
from pathlib import Path
from platform import python_version
from typing import Annotated
from uuid import uuid4

from typer import Abort, Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.cli import settings_app
from mediux_posters.console import CONSOLE
from mediux_posters.constants import Constants
from mediux_posters.mediux import Mediux
from mediux_posters.services import BaseService
from mediux_posters.services._base import BaseCollection, BaseMovie, BaseSeries
from mediux_posters.utils import MediaType, delete_folder

app = Typer()
app.add_typer(settings_app, name="settings")
LOGGER = logging.getLogger("mediux-posters")


def download_posters(
    mediux_data: dict,
    obj: BaseSeries | BaseMovie | BaseCollection,
    mediux: Mediux,
    service: BaseService,
    abort_on_unknown: bool = False,
    debug: bool = False,
) -> None:
    if mediux_data.get("show") and isinstance(obj, BaseSeries):
        mediux.download_series_posters(data=mediux_data, _series=obj, service=service)
    elif mediux_data.get("movie") and isinstance(obj, BaseMovie):
        mediux.download_movie_posters(data=mediux_data, _movie=obj, service=service)
    elif mediux_data.get("collection") and isinstance(obj, BaseCollection):
        mediux.download_collection_posters(data=mediux_data, _collection=obj, service=service)
    else:
        LOGGER.error("Unknown data set: %s", mediux_data)
        if debug:
            with Path(f"{uuid4()}.json").open("w") as stream:
                json.dump(mediux_data, stream, indent=2)
        if abort_on_unknown:
            raise Abort


@app.command(
    name="sync",
    help="Synchronize posters by fetching data from Mediux and updating your libraries.",
)
def sync_posters(
    exclude_libraries: Annotated[
        list[str] | None,
        Option(
            "--skip-library",
            "-l",
            show_default=False,
            default_factory=list,
            help="List of libraries to skip during synchronization. "
            "Specify this option multiple times for skipping multiple libraries.",
        ),
    ],
    clean_cache: Annotated[
        bool,
        Option(
            "--clean",
            "-c",
            show_default=False,
            help="Clean the cache before starting the synchronization process. "
            "Removes all cached files.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        Option(
            "--debug",
            help="Enable debug mode to show extra logging information for troubleshooting.",
        ),
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())
    mediux = Constants.mediux()

    for service in Constants.service_list():
        for mediatype, func in {
            MediaType.SERIES: service.list_series,
            MediaType.COLLECTION: service.list_collections,
            MediaType.MOVIE: service.list_movies,
        }.items():
            with CONSOLE.status(f"[{type(service).__name__}] Fetching {mediatype.value} media"):
                entries = func(exclude_libraries=exclude_libraries)
            for entry in entries:
                LOGGER.info(
                    "[%s] Searching Mediux for '%s' sets",
                    type(service).__name__,
                    entry.display_name,
                )
                set_list = mediux.list_sets(mediatype=entry.mediatype, tmdb_id=entry.tmdb_id)
                if not set_list:
                    continue
                for username in Constants.settings().priority_usernames:
                    if set_data := next(
                        iter(
                            x
                            for x in set_list
                            if x.get("user_created", {}).get("username") == username
                        ),
                        None,
                    ):
                        LOGGER.info(
                            "Downloading '%s' by '%s'",
                            set_data.get("set_name"),
                            set_data.get("user_created", {}).get("username"),
                        )
                        set_data = mediux.scrape_set(set_id=set_data.get("id"))
                        download_posters(
                            mediux_data=set_data,
                            obj=entry,
                            mediux=mediux,
                            service=service,
                            debug=debug,
                        )
                        if entry.all_posters_uploaded:
                            break
                if (
                    not Constants.settings().only_priority_usernames
                    and not entry.all_posters_uploaded
                ):
                    for set_data in set_list:
                        username = set_data.get("user_created", {}).get("username")
                        if username in Constants.settings().exclude_usernames:
                            continue
                        if (
                            Constants.settings().priority_usernames
                            and username in Constants.settings().priority_usernames
                        ):
                            continue
                        LOGGER.info("Downloading '%s' by '%s'", set_data.get("set_name"), username)
                        set_data = mediux.scrape_set(set_id=set_data.get("id"))
                        download_posters(
                            mediux_data=set_data,
                            obj=entry,
                            mediux=mediux,
                            service=service,
                            debug=debug,
                        )
                        if entry.all_posters_uploaded:
                            break


@app.command(name="set", help="Manually set posters for specific Mediux sets using a file or URLs.")
def set_posters(
    file: Annotated[
        Path | None,
        Option(
            dir_okay=False,
            exists=True,
            show_default=False,
            help="Path to a file containing URLs of Mediux sets, one per line. "
            "The file must exist and cannot be a directory.",
        ),
    ] = None,
    urls: Annotated[
        list[str] | None,
        Option(
            "--url",
            "-u",
            show_default=False,
            help="List of URLs of Mediux sets to process. "
            "Specify this option multiple times for multiple URLs.",
        ),
    ] = None,
    clean_cache: Annotated[
        bool,
        Option(
            "--clean",
            "-c",
            show_default=False,
            help="Clean the cache before starting the synchronization process."
            "Removes all cached files.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        Option(
            "--debug",
            help="Enable debug mode to show extra logging information for troubleshooting.",
        ),
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())
    mediux = Constants.mediux()

    url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls
    for entry in url_list:
        if not entry.startswith(f"{Mediux.web_url}/sets"):
            continue
        set_id = int(entry.split("/")[-1])
        set_data = mediux.scrape_set(set_id=set_id)
        LOGGER.info(
            "Downloading '%s' by '%s'",
            set_data.get("set_name"),
            set_data.get("user_created", {}).get("username"),
        )
        tmdb_id = (
            (set_data.get("show") or {}).get("id")
            or (set_data.get("collection") or {}).get("id")
            or (set_data.get("movie") or {}).get("id")
        )
        if tmdb_id:
            tmdb_id = int(tmdb_id)
        for service in Constants.service_list():
            with CONSOLE.status(
                f"Searching {type(service).__name__} for '{set_data.get('set_name')} [{tmdb_id}]'"
            ):
                obj = (
                    service.get_series(tmdb_id=tmdb_id)
                    or service.get_collection(tmdb_id=tmdb_id)
                    or service.get_movie(tmdb_id=tmdb_id)
                )
            if not obj:
                LOGGER.warning(
                    "[%s] Unable to find '%s [%d]'",
                    type(service).__name__,
                    set_data.get("set_name"),
                    tmdb_id,
                )
                continue
            download_posters(
                mediux_data=set_data,
                obj=obj,
                mediux=mediux,
                service=service,
                abort_on_unknown=True,
                debug=debug,
            )


if __name__ == "__main__":
    app(prog_name="Mediux-Posters")
