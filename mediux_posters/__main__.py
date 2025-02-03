import json
import logging
from collections.abc import Callable, Generator
from enum import Enum
from pathlib import Path
from platform import python_version
from typing import Annotated
from uuid import uuid4

from plexapi.exceptions import Unauthorized
from typer import Abort, Context, Exit, Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.console import CONSOLE
from mediux_posters.mediux import Mediux
from mediux_posters.services import BaseService, Jellyfin, Plex
from mediux_posters.services._base import BaseCollection, BaseMovie, BaseShow
from mediux_posters.settings import Settings
from mediux_posters.utils import MediaType, delete_folder, slugify

app = Typer()
LOGGER = logging.getLogger("mediux-posters")


@app.callback(invoke_without_command=True)
def common(
    ctx: Context,
    version: Annotated[
        bool | None, Option("--version", is_eager=True, help="Show the version and exit.")
    ] = None,
) -> None:
    if ctx.invoked_subcommand:
        return
    if version:
        CONSOLE.print(f"Mediux Posters v{__version__}")
        raise Exit


@app.command(name="settings", help="Display the current and default settings.")
def view_settings() -> None:
    Settings.load().display()


def setup(
    full_clean: bool = False, debug: bool = False
) -> tuple[Settings, Mediux, list[BaseService]]:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

    if full_clean:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())
    settings = Settings.load()
    settings.save()
    service_list = []
    if settings.jellyfin.token:
        service_list.append(Jellyfin(settings=settings.jellyfin))
    try:
        if settings.plex.token:
            service_list.append(Plex(settings=settings.plex))
    except Unauthorized as err:
        LOGGER.warning(err)
    return settings, Mediux(), service_list


def filter_sets(
    set_list: list[dict], settings: Settings, mediux: Mediux
) -> Generator[dict, None, None]:
    if not set_list:
        return

    # Yield priority usernames first
    for username in settings.priority_usernames:
        for set_data in [
            x for x in set_list if x.get("user_created", {}).get("username") == username
        ]:
            yield mediux.scrape_set(set_id=set_data.get("id"))

    # If allowed, yield remaining sets
    if not settings.only_priority_usernames:
        for set_data in set_list:
            username = set_data.get("user_created", {}).get("username")
            if username in settings.exclude_usernames:
                continue
            if settings.priority_usernames and username in settings.priority_usernames:
                continue
            yield mediux.scrape_set(set_id=set_data.get("id"))


def update_posters(
    mediux_data: dict,
    obj: BaseShow | BaseMovie | BaseCollection,
    mediux: Mediux,
    service: BaseService,
    abort_on_unknown: bool = False,
    debug: bool = False,
) -> None:
    if mediux_data.get("show") and isinstance(obj, BaseShow):
        mediux.download_show_posters(data=mediux_data, show=obj)
        service.upload_posters(obj=obj)
        for season in obj.seasons:
            service.upload_posters(obj=season)
            for episode in season.episodes:
                service.upload_posters(obj=episode)
    elif mediux_data.get("movie") and isinstance(obj, BaseMovie):
        mediux.download_movie_posters(data=mediux_data, movie=obj)
        service.upload_posters(obj=obj)
    elif mediux_data.get("collection") and isinstance(obj, BaseCollection):
        mediux.download_collection_posters(data=mediux_data, collection=obj)
        service.upload_posters(obj=obj)
        for movie_data in mediux_data.get("collection", {}).get("movies", []):
            if movie := service.get_movie(tmdb_id=int(movie_data.get("id", -1))):
                mediux.download_movie_posters(data=mediux_data, movie=movie)
                service.upload_posters(obj=movie)
            else:
                LOGGER.warning(
                    "[%s] Unable to find '%s (%s)'",
                    type(service).__name__,
                    movie_data.get("title"),
                    (movie_data.get("release_date") or "0000")[:4],
                )
    else:
        LOGGER.error("Unknown data set: %s", mediux_data)
        if debug:
            with Path(f"{uuid4()}.json").open("w") as stream:
                json.dump(mediux_data, stream, indent=2)
        if abort_on_unknown:
            raise Abort


class MediaTypeChoice(str, Enum):
    SHOW = MediaType.SHOW.value
    COLLECTION = MediaType.COLLECTION.value
    MOVIE = MediaType.MOVIE.value


@app.command(
    name="sync", help="Synchronize posters by fetching data from Mediux and updating your services."
)
def sync_posters(
    skip_mediatypes: Annotated[
        list[MediaTypeChoice] | None,
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
        list[str] | None,
        Option(
            "--skip-library",
            "-L",
            show_default=False,
            default_factory=list,
            help="List of libraries to skip. "
            "Specify this option multiple times for skipping multiple libraries.",
        ),
    ],
    start: Annotated[
        int, Option("--start", "-s", help="The starting index for processing media.")
    ] = 0,
    end: Annotated[
        int, Option("--end", "-e", help="The ending index for processing media.")
    ] = 100_000,
    full_clean: Annotated[
        bool,
        Option(
            "--full-clean", "-C", show_default=False, help="Delete the whole cache before starting."
        ),
    ] = False,
    simple_clean: Annotated[
        bool,
        Option(
            "--simple-clean",
            "-c",
            show_default=False,
            help="Delete the cache of each media instead of the whole cache.",
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
    settings, mediux, service_list = setup(full_clean=full_clean, debug=debug)
    skip_mediatypes = [x.value for x in skip_mediatypes]

    for idx, service in enumerate(service_list):
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        media_dict: dict[
            MediaType,
            Callable[[list[str] | None], list[BaseShow] | list[BaseCollection] | list[BaseMovie]],
        ] = {
            MediaType.SHOW: service.list_shows,
            MediaType.COLLECTION: service.list_collections,
            MediaType.MOVIE: service.list_movies,
        }
        for mediatype, func in media_dict.items():
            if mediatype.value in skip_mediatypes:
                continue
            with CONSOLE.status(f"[{type(service).__name__}] Fetching {mediatype.value} media"):
                entries = func(skip_libraries=skip_libraries)[start:end]
            for index, entry in enumerate(entries):
                CONSOLE.rule(
                    f"[{index + 1}/{len(entries)}] {entry.display_name} [{entry.tmdb_id}]",
                    align="left",
                    style="subtitle",
                )
                if simple_clean:
                    LOGGER.info("Cleaning %s cache", entry.display_name)
                    delete_folder(
                        folder=get_cache_root()
                        / "covers"
                        / entry.mediatype.value
                        / slugify(entry.display_name)
                    )
                LOGGER.info(
                    "[%s] Searching Mediux for '%s' sets",
                    type(service).__name__,
                    entry.display_name,
                )
                set_list = mediux.list_sets(mediatype=mediatype, tmdb_id=entry.tmdb_id)
                for set_data in filter_sets(set_list=set_list, settings=settings, mediux=mediux):
                    LOGGER.info(
                        "Downloading '%s' by '%s'",
                        set_data.get("set_name"),
                        set_data.get("user_created", {}).get("username"),
                    )
                    update_posters(
                        mediux_data=set_data, obj=entry, mediux=mediux, service=service, debug=debug
                    )
                    if entry.all_posters_uploaded:
                        break


@app.command(
    name="show", help="Manually set posters for specific Mediux shows using a file or URLs."
)
def show_posters(
    file: Annotated[
        Path | None,
        Option(
            dir_okay=False,
            exists=True,
            show_default=False,
            help="Path to a file containing URLs of Mediux shows, one per line. "
            "If set, the file must exist and cannot be a directory.",
        ),
    ] = None,
    urls: Annotated[
        list[str] | None,
        Option(
            "--url",
            "-u",
            show_default=False,
            help="List of URLs of Mediux shows to process. "
            "Specify this option multiple times for multiple URLs.",
        ),
    ] = None,
    full_clean: Annotated[
        bool,
        Option(
            "--full-clean", "-C", show_default=False, help="Delete the whole cache before starting."
        ),
    ] = False,
    simple_clean: Annotated[
        bool,
        Option(
            "--simple-clean",
            "-c",
            show_default=False,
            help="Delete the cache of each media instead of the whole cache.",
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
    settings, mediux, service_list = setup(full_clean=full_clean, debug=debug)

    for idx, service in enumerate(service_list):
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls
        for index, entry in enumerate(url_list):
            if not entry.startswith(f"{Mediux.web_url}/shows"):
                continue
            tmdb_id = int(entry.split("/")[-1])
            with CONSOLE.status(f"Searching {type(service).__name__} for TMDB id: '{tmdb_id}'"):
                obj = service.get_show(tmdb_id=tmdb_id)
                if not obj:
                    LOGGER.warning("[%s] Unable to find '%d'", type(service).__name__, tmdb_id)
                    continue
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {obj.display_name} [{obj.tmdb_id}]",
                align="left",
                style="subtitle",
            )
            if simple_clean:
                LOGGER.info("Cleaning %s cache", obj.display_name)
                delete_folder(
                    folder=get_cache_root()
                    / "covers"
                    / obj.mediatype.value
                    / slugify(obj.display_name)
                )
            set_list = mediux.list_sets(mediatype=MediaType.SHOW, tmdb_id=tmdb_id)
            for set_data in filter_sets(set_list=set_list, settings=settings, mediux=mediux):
                LOGGER.info(
                    "Downloading '%s' by '%s'",
                    set_data.get("set_name"),
                    set_data.get("user_created", {}).get("username"),
                )
                update_posters(
                    mediux_data=set_data, obj=obj, mediux=mediux, service=service, debug=debug
                )
                if obj.all_posters_uploaded:
                    break


@app.command(
    name="collection",
    help="Manually set posters for specific Mediux collections using a file or URLs.",
)
def collection_posters(
    file: Annotated[
        Path | None,
        Option(
            dir_okay=False,
            exists=True,
            show_default=False,
            help="Path to a file containing URLs of Mediux collections, one per line. "
            "If set, the file must exist and cannot be a directory.",
        ),
    ] = None,
    urls: Annotated[
        list[str] | None,
        Option(
            "--url",
            "-u",
            show_default=False,
            help="List of URLs of Mediux collections to process. "
            "Specify this option multiple times for multiple URLs.",
        ),
    ] = None,
    full_clean: Annotated[
        bool,
        Option(
            "--full-clean", "-C", show_default=False, help="Delete the whole cache before starting."
        ),
    ] = False,
    simple_clean: Annotated[
        bool,
        Option(
            "--simple-clean",
            "-c",
            show_default=False,
            help="Delete the cache of each media instead of the whole cache.",
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
    settings, mediux, service_list = setup(full_clean=full_clean, debug=debug)

    for idx, service in enumerate(service_list):
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls
        for index, entry in enumerate(url_list):
            if not entry.startswith(f"{Mediux.web_url}/collections"):
                continue
            tmdb_id = int(entry.split("/")[-1])
            with CONSOLE.status(f"Searching {type(service).__name__} for TMDB id: '{tmdb_id}'"):
                obj = service.get_collection(tmdb_id=tmdb_id)
                if not obj:
                    LOGGER.warning("[%s] Unable to find '%d'", type(service).__name__, tmdb_id)
                    continue
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {obj.display_name} [{obj.tmdb_id}]",
                align="left",
                style="subtitle",
            )
            if simple_clean:
                LOGGER.info("Cleaning %s cache", obj.display_name)
                delete_folder(
                    folder=get_cache_root()
                    / "covers"
                    / obj.mediatype.value
                    / slugify(obj.display_name)
                )
            set_list = mediux.list_sets(mediatype=MediaType.COLLECTION, tmdb_id=tmdb_id)
            for set_data in filter_sets(set_list=set_list, settings=settings, mediux=mediux):
                LOGGER.info(
                    "Downloading '%s' by '%s'",
                    set_data.get("set_name"),
                    set_data.get("user_created", {}).get("username"),
                )
                update_posters(
                    mediux_data=set_data, obj=obj, mediux=mediux, service=service, debug=debug
                )
                if obj.all_posters_uploaded:
                    break


@app.command(
    name="movie", help="Manually set posters for specific Mediux movies using a file or URLs."
)
def movie_posters(
    file: Annotated[
        Path | None,
        Option(
            dir_okay=False,
            exists=True,
            show_default=False,
            help="Path to a file containing URLs of Mediux movies, one per line. "
            "If set, the file must exist and cannot be a directory.",
        ),
    ] = None,
    urls: Annotated[
        list[str] | None,
        Option(
            "--url",
            "-u",
            show_default=False,
            help="List of URLs of Mediux movies to process. "
            "Specify this option multiple times for multiple URLs.",
        ),
    ] = None,
    full_clean: Annotated[
        bool,
        Option(
            "--full-clean", "-C", show_default=False, help="Delete the whole cache before starting."
        ),
    ] = False,
    simple_clean: Annotated[
        bool,
        Option(
            "--simple-clean",
            "-c",
            show_default=False,
            help="Delete the cache of each media instead of the whole cache.",
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
    settings, mediux, service_list = setup(full_clean=full_clean, debug=debug)

    for idx, service in enumerate(service_list):
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls
        for index, entry in enumerate(url_list):
            if not entry.startswith(f"{Mediux.web_url}/movies"):
                continue
            tmdb_id = int(entry.split("/")[-1])
            with CONSOLE.status(f"Searching {type(service).__name__} for TMDB id: '{tmdb_id}'"):
                obj = service.get_movie(tmdb_id=tmdb_id)
                if not obj:
                    LOGGER.warning("[%s] Unable to find '%d'", type(service).__name__, tmdb_id)
                    continue
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {obj.display_name} [{obj.tmdb_id}]",
                align="left",
                style="subtitle",
            )
            if simple_clean:
                LOGGER.info("Cleaning %s cache", obj.display_name)
                delete_folder(
                    folder=get_cache_root()
                    / "covers"
                    / obj.mediatype.value
                    / slugify(obj.display_name)
                )
            set_list = mediux.list_sets(mediatype=MediaType.MOVIE, tmdb_id=tmdb_id)
            for set_data in filter_sets(set_list=set_list, settings=settings, mediux=mediux):
                LOGGER.info(
                    "Downloading '%s' by '%s'",
                    set_data.get("set_name"),
                    set_data.get("user_created", {}).get("username"),
                )
                update_posters(
                    mediux_data=set_data, obj=obj, mediux=mediux, service=service, debug=debug
                )
                if obj.all_posters_uploaded:
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
            "If set, the file must exist and cannot be a directory.",
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
    full_clean: Annotated[
        bool,
        Option(
            "--full-clean", "-C", show_default=False, help="Delete the whole cache before starting."
        ),
    ] = False,
    simple_clean: Annotated[
        bool,
        Option(
            "--simple-clean",
            "-c",
            show_default=False,
            help="Delete the cache of each media instead of the whole cache.",
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
    settings, mediux, service_list = setup(full_clean=full_clean, debug=debug)

    for idx, service in enumerate(service_list):
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls
        for index, entry in enumerate(url_list):
            if not entry.startswith(f"{Mediux.web_url}/sets"):
                continue
            set_id = int(entry.split("/")[-1])
            set_data = mediux.scrape_set(set_id=set_id)
            tmdb_id = (
                (set_data.get("show") or {}).get("id")
                or (set_data.get("collection") or {}).get("id")
                or (set_data.get("movie") or {}).get("id")
            )
            if tmdb_id:
                tmdb_id = int(tmdb_id)
            with CONSOLE.status(
                f"Searching {type(service).__name__} for '{set_data.get('set_name')} [{tmdb_id}]'"
            ):
                obj = (
                    service.get_show(tmdb_id=tmdb_id)
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
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {obj.display_name} [{obj.tmdb_id}]",
                align="left",
                style="subtitle",
            )
            if simple_clean:
                LOGGER.info("Cleaning %s cache", obj.display_name)
                delete_folder(
                    folder=get_cache_root()
                    / "covers"
                    / obj.mediatype.value
                    / slugify(obj.display_name)
                )
            LOGGER.info(
                "Downloading '%s' by '%s'",
                set_data.get("set_name"),
                set_data.get("user_created", {}).get("username"),
            )
            update_posters(
                mediux_data=set_data,
                obj=obj,
                mediux=mediux,
                service=service,
                abort_on_unknown=True,
                debug=debug,
            )


if __name__ == "__main__":
    app(prog_name="Mediux-Posters")
