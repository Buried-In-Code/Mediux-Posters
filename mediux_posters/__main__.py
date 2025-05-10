import logging
from collections.abc import Generator
from enum import Enum
from pathlib import Path
from platform import python_version
from typing import Annotated, Protocol, TypeVar

from plexapi.exceptions import Unauthorized
from typer import Abort, Context, Exit, Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.errors import ServiceError
from mediux_posters.mediux import CollectionSet, File, FileType, Mediux, MovieSet, ShowSet
from mediux_posters.services import (
    BaseService,
    Collection,
    Episode,
    Jellyfin,
    Movie,
    Plex,
    Season,
    Show,
)
from mediux_posters.settings import Settings
from mediux_posters.utils import CONSOLE, MediaType, delete_folder, get_cached_image, slugify

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
        LOGGER.info("Cleaning Cache: %s", get_cache_root())
        delete_folder(folder=get_cache_root())
    settings = Settings.load().save()
    if not settings.mediux.api_key:
        LOGGER.fatal("Mediux Posters requires a Mediux ApiKey to be set.")
        raise Abort
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


def find_file(files: list[File], file_type: FileType, id_value: int) -> File | None:
    id_fields = ["show_id", "season_id", "episode_id", "collection_id", "movie_id"]
    for x in files:
        if x.file_type != file_type:
            continue
        for field in id_fields:
            if getattr(x, field, None) == id_value:
                return x
    return None


def process_image(
    entry: Show | Season | Episode | Collection | Movie,
    file_type: FileType,
    set_data: ShowSet | CollectionSet | MovieSet,
    id_value: int,
    parent: str,
    filename: str,
    should_log: bool,
    mediux: Mediux,
    service: BaseService,
    kometa_integration: bool = False,
) -> bool:
    attribute = f"{file_type.name.lower()}_uploaded"
    if not getattr(entry, attribute) and (
        file_info := find_file(files=set_data.files, file_type=file_type, id_value=id_value)
    ):
        image_file = get_cached_image(parent, filename)
        if image_file.exists():
            setattr(entry, attribute, True)
        else:
            if should_log:
                LOGGER.info("Downloading '%s' by '%s'", set_data.set_title, set_data.username)
                should_log = False
            mediux.download_image(file_id=file_info.id, output=image_file)
            setattr(
                entry,
                attribute,
                service.upload_image(
                    obj=entry, image_file=image_file, kometa_integration=kometa_integration
                ),
            )
    return should_log


def process_set_data(
    entry: Show | Season | Episode | Collection | Movie,
    set_data: ShowSet | CollectionSet | MovieSet,
    mediux: Mediux,
    service: BaseService,
    media_type: MediaType,
    kometa_integration: bool = False,
) -> bool:
    should_log = True
    if entry.all_posters_uploaded:
        LOGGER.info("All posters have been uploaded, skipping remaining sets")
        return False

    should_log = process_image(
        entry=entry,
        file_type=FileType.POSTER,
        set_data=set_data,
        id_value=entry.tmdb_id,
        parent=slugify(value=entry.display_name),
        filename=f"{FileType.POSTER}.jpg",
        should_log=should_log,
        mediux=mediux,
        service=service,
        kometa_integration=kometa_integration,
    )
    should_log = process_image(
        entry=entry,
        file_type=FileType.BACKDROP,
        set_data=set_data,
        id_value=entry.tmdb_id,
        parent=slugify(value=entry.display_name),
        filename=f"{FileType.BACKDROP}.jpg",
        should_log=should_log,
        mediux=mediux,
        service=service,
        kometa_integration=kometa_integration,
    )
    if media_type is MediaType.SHOW:
        for season in entry.seasons:
            mediux_season = next(
                (x for x in set_data.show.seasons if x.number == season.number), None
            )
            if not mediux_season:
                continue
            should_log = process_image(
                entry=season,
                file_type=FileType.POSTER,
                set_data=set_data,
                id_value=mediux_season.id,
                parent=slugify(value=entry.display_name),
                filename=f"s{season.number:02}.jpg",
                should_log=should_log,
                mediux=mediux,
                service=service,
                kometa_integration=kometa_integration,
            )
            for episode in season.episodes:
                mediux_episode = next(
                    (x for x in mediux_season.episodes if x.number == episode.number), None
                )
                if not mediux_episode:
                    continue
                should_log = process_image(
                    entry=episode,
                    file_type=FileType.TITLE_CARD,
                    set_data=set_data,
                    id_value=mediux_episode.id,
                    parent=slugify(value=entry.display_name),
                    filename=f"s{season.number:02}e{episode.number:02}.jpg",
                    should_log=should_log,
                    mediux=mediux,
                    service=service,
                    kometa_integration=kometa_integration,
                )
    elif media_type is MediaType.COLLECTION:
        for movie in entry.movies:
            mediux_movie = next(
                (x for x in set_data.collection.movies if x.tmdb_id == movie.tmdb_id), None
            )
            if not mediux_movie:
                continue
            should_log = process_image(
                entry=movie,
                file_type=FileType.POSTER,
                set_data=set_data,
                id_value=movie.tmdb_id,
                parent=slugify(value=movie.display_name),
                filename=f"{FileType.POSTER}.jpg",
                should_log=should_log,
                mediux=mediux,
                service=service,
                kometa_integration=kometa_integration,
            )
            should_log = process_image(
                entry=movie,
                file_type=FileType.BACKDROP,
                set_data=set_data,
                id_value=movie.tmdb_id,
                parent=slugify(value=movie.display_name),
                filename=f"{FileType.BACKDROP}.jpg",
                should_log=should_log,
                mediux=mediux,
                service=service,
                kometa_integration=kometa_integration,
            )
    return True


class ServiceChoice(str, Enum):
    PLEX = Plex.__name__
    JELLYFIN = Jellyfin.__name__


@app.command(
    name="sync", help="Synchronize posters by fetching data from Mediux and updating your services."
)
def sync_posters(
    skip_services: Annotated[
        list[ServiceChoice],
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
    skip_services = [x.value for x in skip_services]

    for idx, service in enumerate(service_list):
        if type(service).__name__ in skip_services:
            continue
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )

        for media_type in MediaType:
            if media_type in skip_media_types:
                continue

            try:
                with CONSOLE.status(
                    f"[{type(service).__name__}] Fetching {media_type.value} media"
                ):
                    entries = service.list(media_type=media_type, skip_libraries=skip_libraries)[
                        start:end
                    ]
            except ServiceError as err:
                LOGGER.warning("[%s] %s", type(service).__name__, err)
                break
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
                try:
                    set_list = mediux.list_sets(
                        media_type=media_type,
                        tmdb_id=entry.tmdb_id,
                        exclude_usernames=settings.exclude_usernames,
                    )
                except ServiceError as err:
                    LOGGER.error(err)
                    set_list = []

                filtered_sets = filter_sets(
                    set_list=set_list,
                    priority_usernames=settings.priority_usernames,
                    only_priority_usernames=settings.only_priority_usernames,
                )
                for set_data in filtered_sets:
                    if not process_set_data(
                        entry=entry,
                        set_data=set_data,
                        mediux=mediux,
                        service=service,
                        media_type=media_type,
                        kometa_integration=settings.kometa_integration,
                    ):
                        break


@app.command(
    name="media", help="Manually set posters for specific Mediux media using a file or URLs."
)
def media_posters(
    skip_services: Annotated[
        list[ServiceChoice],
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
    skip_services = [x.value for x in skip_services]
    url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls

    for idx, service in enumerate(service_list):
        if type(service).__name__ in skip_services:
            continue
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )

        for index, url in enumerate(url_list):
            media_type = None
            for type_key in MediaType:
                if url.startswith(f"{Mediux.WEB_URL}/{type_key}s"):
                    media_type = type_key
                    break
            if not media_type:
                LOGGER.warning("Unknown Mediux url: '%s'", url)
                continue

            tmdb_id = int(url.split("/")[-1])
            try:
                with CONSOLE.status(f"Searching {type(service).__name__} for TMDB id: '{tmdb_id}'"):
                    entry = service.get(media_type=media_type, tmdb_id=tmdb_id)
                    if not entry:
                        LOGGER.warning(
                            "[%s] Unable to find a %s with a Tmdb Id of '%d'",
                            type(service).__name__,
                            media_type.value.capitalize(),
                            tmdb_id,
                        )
                        continue
            except ServiceError as err:
                LOGGER.warning("[%s] %s", type(service).__name__, err)
                break
            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {entry.display_name} [tmdb-{entry.tmdb_id}]",
                align="left",
                style="subtitle",
            )
            if simple_clean:
                LOGGER.info("Cleaning %s cache", entry.display_name)
                delete_folder(folder=get_cached_image(slugify(value=entry.display_name)))
                if media_type is MediaType.COLLECTION:
                    for movie in entry.movies:
                        delete_folder(folder=get_cached_image(slugify(value=movie.display_name)))

            try:
                set_list = mediux.list_sets(
                    media_type=media_type,
                    tmdb_id=tmdb_id,
                    exclude_usernames=settings.exclude_usernames,
                )
            except ServiceError as err:
                if debug:
                    LOGGER.error(err)
                set_list = []

            filtered_sets = filter_sets(
                set_list=set_list,
                priority_usernames=settings.priority_usernames,
                only_priority_usernames=settings.only_priority_usernames,
            )
            for set_data in filtered_sets:
                if not process_set_data(
                    entry=entry,
                    set_data=set_data,
                    mediux=mediux,
                    service=service,
                    media_type=media_type,
                    kometa_integration=settings.kometa_integration,
                ):
                    break


@app.command(name="set", help="Manually set posters for specific Mediux sets using a file or URLs.")
def set_posters(
    skip_services: Annotated[
        list[ServiceChoice],
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
    skip_services = [x.value for x in skip_services]
    url_list = [x.strip() for x in file.read_text().splitlines()] if file else urls

    for idx, service in enumerate(service_list):
        if type(service).__name__ in skip_services:
            continue
        CONSOLE.rule(
            f"[{idx + 1}/{len(service_list)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )

        for index, url in enumerate(url_list):
            if not url.startswith(f"{Mediux.WEB_URL}/sets"):
                continue
            set_id = int(url.split("/")[-1])
            set_data = (
                mediux.get_show_set(set_id=set_id)
                or mediux.get_collection_set(set_id=set_id)
                or mediux.get_movie_set(set_id=set_id)
            )
            if not set_data:
                LOGGER.warning("[Mediux] Unable to find a Set with an Id of '%d'", set_id)
                continue

            media_type, tmdb_id = (
                (MediaType.SHOW, set_data.show.tmdb_id)
                if isinstance(set_data, ShowSet)
                else (MediaType.COLLECTION, set_data.collection.tmdb_id)
                if isinstance(set_data, CollectionSet)
                else (MediaType.MOVIE, set_data.movie.tmdb_id)
                if isinstance(set_data, MovieSet)
                else (None, None)
            )
            if not tmdb_id:
                LOGGER.error("Set does not contain a TmdbId, this should not be possible")
                continue

            CONSOLE.rule(
                f"[{index + 1}/{len(url_list)}] {set_data.set_title} [tmdb-{tmdb_id}]",
                align="left",
                style="subtitle",
            )
            try:
                with CONSOLE.status(
                    f"Searching {type(service).__name__} for '{set_data.set_title} [{tmdb_id}]'"
                ):
                    entry = service.get(media_type=media_type, tmdb_id=tmdb_id)
                    if not entry:
                        LOGGER.warning(
                            "[%s] Unable to find any media with a Tmdb Id of '%d'",
                            type(service).__name__,
                            tmdb_id,
                        )
                        continue
            except ServiceError as err:
                LOGGER.warning("[%s] %s", type(service).__name__, err)
                break
            if simple_clean:
                LOGGER.info("Cleaning %s cache", entry.display_name)
                delete_folder(folder=get_cached_image(slugify(value=entry.display_name)))
                if media_type is MediaType.COLLECTION:
                    for movie in entry.movies:
                        delete_folder(folder=get_cached_image(slugify(value=movie.display_name)))

            process_set_data(
                entry=entry,
                set_data=set_data,
                mediux=mediux,
                service=service,
                media_type=media_type,
                kometa_integration=settings.kometa_integration,
            )
