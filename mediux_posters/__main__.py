import logging
from collections.abc import Generator
from enum import Enum
from pathlib import Path
from platform import python_version
from typing import Annotated, Protocol, TypeVar

from plexapi.exceptions import Unauthorized
from typer import Context, Exit, Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.constants import CONSOLE
from mediux_posters.errors import ServiceError
from mediux_posters.mediux import CollectionSet, Mediux, MovieSet, ShowSet
from mediux_posters.services import BaseService, Collection, Jellyfin, Plex
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
    settings = Settings.load().save()
    if not settings.mediux.api_key:
        LOGGER.fatal("Mediux Posters requires a Mediux ApiKey to be set.")
        raise Exit
    mediux = Mediux(base_url=settings.mediux.base_url, api_key=settings.mediux.api_key)
    service_list = []
    try:
        if settings.plex.token:
            service_list.append(Plex(base_url=settings.plex.base_url, token=settings.plex.token))
    except Unauthorized as err:
        LOGGER.warning(err)
    if settings.jellyfin.token:
        service_list.append(
            Jellyfin(base_url=settings.jellyfin.base_url, token=settings.jellyfin.token)
        )
    return settings, mediux, service_list


T = TypeVar("T", bound="MediuxSet")


class MediuxSet(Protocol):
    username: str


def filter_sets(
    set_list: list[T], priority_usernames: list[str], only_priority_usernames: bool
) -> Generator[T]:
    if not set_list:
        return

    # Yield priority usernames first
    for username in priority_usernames:
        yield from [x for x in set_list if x.username == username]

    # If allowed, yield remaining sets
    if not only_priority_usernames:
        yield from [x for x in set_list if x.username not in priority_usernames]


class MediaTypeChoice(str, Enum):
    SHOW = MediaType.SHOW.value
    COLLECTION = MediaType.COLLECTION.value
    MOVIE = MediaType.MOVIE.value


@app.command(
    name="sync", help="Synchronize posters by fetching data from Mediux and updating your services."
)
def sync_posters(
    skip_mediatypes: Annotated[
        list[MediaTypeChoice],
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
            "Specify this option multiple times for skipping multiple libraries. ",
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
        for media_type in MediaType:
            if media_type.value in skip_mediatypes:
                continue
            with CONSOLE.status(
                f"[{type(service).__name__}] Fetching {media_type.name.lower().capitalize()} media"
            ):
                entries = service.list(media_type=media_type, skip_libraries=skip_libraries)[
                    start:end
                ]
            for index, entry in enumerate(entries):
                CONSOLE.rule(
                    f"[{index + 1}/{len(entries)}] {entry.display_name} [tmdb-{entry.tmdb_id}]",
                    align="left",
                    style="subtitle",
                )
                LOGGER.info(
                    "[%s] Searching Mediux for '%s' sets",
                    type(service).__name__,
                    entry.display_name,
                )
                set_list = mediux.list_sets(media_type=media_type, tmdb_id=entry.tmdb_id)
                for set_data in filter_sets(set_list=set_list, settings=settings, mediux=mediux):
                    LOGGER.info("Downloading '%s' by '%s'", set_data.set_title, set_data.username)


@app.command(
    name="manual", help="Manually set posters for specific Mediux media using a file or URLs."
)
def manual_posters(
    urls: Annotated[
        list[str],
        Option(
            "--url",
            "-u",
            default_factory=list,
            show_default=False,
            help="List of URLs from Mediux to process. "
            "Specify this option multiple times for multiple URLs.",
        ),
    ],
    file: Annotated[
        Path | None,
        Option(
            dir_okay=False,
            exists=True,
            show_default=False,
            help="Path to a file containing URLs from Mediux, one per line. "
            "If set, the file must exist and cannot be a directory.",
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
            if entry.startswith(f"{Mediux.WEB_URL}/sets"):
                set_posters(
                    settings=settings,
                    mediux=mediux,
                    service=service,
                    url=entry,
                    simple_clean=simple_clean,
                    debug=debug,
                )
                continue
            media_type = (
                MediaType.SHOW
                if entry.startswith(f"{Mediux.WEB_URL}/{MediaType.SHOW}s")
                else MediaType.COLLECTION
                if entry.startswith(f"{Mediux.WEB_URL}/{MediaType.COLLECTION}s")
                else MediaType.MOVIE
                if entry.startswith(f"{Mediux.WEB_URL}/{MediaType.MOVIE}s")
                else None
            )
            if not media_type:
                continue
            tmdb_id = int(entry.split("/")[-1])
            with CONSOLE.status(f"Searching {type(service).__name__} for TMDB id: '{tmdb_id}'"):
                obj = service.get(media_type=media_type, tmdb_id=tmdb_id)
                if not obj:
                    LOGGER.warning(
                        "[%s] Unable to find a %s with a Tmdb Id of '%d'",
                        type(service).__name__,
                        media_type,
                        tmdb_id,
                    )
                    continue
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {obj.display_name} [tmdb-{obj.tmdb_id}]",
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
                if isinstance(obj, Collection):
                    for movie in obj.movies:
                        delete_folder(
                            folder=get_cache_root()
                            / "covers"
                            / movie.mediatype.value
                            / slugify(movie.display_name)
                        )
            try:
                set_list = mediux.list_sets(
                    media_type=media_type,
                    tmdb_id=tmdb_id,
                    exclude_usernames=settings.exclude_usernames,
                )
            except ServiceError as err:
                LOGGER.error(err)
                set_list = []
            for set_data in filter_sets(
                set_list=set_list,
                priority_usernames=settings.priority_usernames,
                only_priority_usernames=settings.only_priority_usernames,
            ):
                LOGGER.info("Downloading '%s' by '%s'", set_data.set_title, set_data.username)


def set_posters(
    settings: Settings,  # noqa: ARG001
    mediux: Mediux,
    service: BaseService,
    url: str,
    simple_clean: bool = False,
    debug: bool = False,  # noqa: ARG001
) -> None:
    set_id = int(url.split("/")[-1])
    set_data = (
        mediux.get_show_set(set_id=set_id)
        or mediux.get_collection_set(set_id=set_id)
        or mediux.get_movie_set(set_id=set_id)
    )
    if tmdb_id := (
        set_data.show.tmdb_id
        if isinstance(set_data, ShowSet)
        else set_data.collection.tmdb_id
        if isinstance(set_data, CollectionSet)
        else set_data.movie.tmdb_id
        if isinstance(set_data, MovieSet)
        else None
    ):
        return

    with CONSOLE.status(
        f"Searching {type(service).__name__} for '{set_data.set_title} [{tmdb_id}]'"
    ):
        obj = service.find(tmdb_id=tmdb_id)
        if not obj:
            LOGGER.warning(
                "[%s] Unable to find any media with a Tmdb Id of '%d'",
                type(service).__name__,
                tmdb_id,
            )
            return

    if simple_clean:
        LOGGER.info("Cleaning %s cache", obj.display_name)
        delete_folder(
            folder=get_cache_root() / "covers" / obj.mediatype.value / slugify(obj.display_name)
        )
        if isinstance(obj, Collection):
            for movie in obj.movies:
                delete_folder(
                    folder=get_cache_root()
                    / "covers"
                    / movie.mediatype.value
                    / slugify(movie.display_name)
                )
    LOGGER.info("Downloading '%s' by '%s'", set_data.set_title, set_data.username)


if __name__ == "__main__":
    app(prog_name="Mediux-Posters")
