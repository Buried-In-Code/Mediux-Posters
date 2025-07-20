import logging
from collections.abc import Generator
from enum import Enum
from platform import python_version
from typing import Annotated, Final, Protocol, TypeVar

from typer import Abort, Argument, Context, Exit, Option, Typer

from mediux_posters import __project__, __version__, get_cache_root, setup_logging
from mediux_posters.cli import settings_app
from mediux_posters.console import CONSOLE
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
from mediux_posters.utils import MediaType, delete_folder, get_cached_image, slugify

LOGGER = logging.getLogger(__project__)
app = Typer(no_args_is_help=True)
app.add_typer(settings_app, name="settings")

# Constants
DEFAULT_CREATOR_RANK: Final[int] = 1_000_000
MAX_IMAGE_SIZE: Final[int] = 10_000_000  # 10 MB


class ServiceOption(str, Enum):
    PLEX = Plex.__name__
    JELLYFIN = Jellyfin.__name__


def setup(
    skip_services: list[ServiceOption], clean: bool, debug: bool = False
) -> tuple[Settings, Mediux, list[BaseService]]:
    setup_logging(debug=debug)
    LOGGER.info("%s v%s", __project__.title(), __version__)
    LOGGER.info("Python v%s", python_version())

    if clean:
        LOGGER.info("Cleaning cache directory: '%s'", get_cache_root())
        delete_folder(folder=get_cache_root())

    settings = Settings.load().save()

    if not settings.mediux.token:
        LOGGER.error("Missing Mediux token, check your settings")
        raise Abort
    mediux = Mediux(base_url=settings.mediux.base_url, token=settings.mediux.token)
    if not mediux.validate():
        raise Abort

    services = []
    skip_services = [x.value for x in skip_services]
    if Plex.__name__ not in skip_services and settings.plex.token:
        plex = Plex(base_url=settings.plex.base_url, token=settings.plex.token)
        if plex.validate():
            services.append(plex)
    if Jellyfin.__name__ not in skip_services and settings.jellyfin.token:
        jellyfin = Jellyfin(base_url=settings.jellyfin.base_url, token=settings.jellyfin.token)
        if jellyfin.validate():
            services.append(jellyfin)
    if not services:
        LOGGER.error("No services configured, check your settings")
        raise Abort

    return settings, mediux, services


T = TypeVar("T", bound="MediuxSet")


class MediuxSet(Protocol):
    username: str


def filter_sets(
    set_list: list[T], priority_usernames: list[str], only_priority_usernames: bool
) -> Generator[T]:
    if not set_list:
        return
    # Priority usernames first
    for username in priority_usernames:
        yield from [x for x in set_list if x.username == username]
    if not only_priority_usernames:
        # Remaining sets
        yield from [x for x in set_list if x.username not in priority_usernames]


def process_set_data(
    entry: Show | Collection | Movie,
    set_data: ShowSet | CollectionSet | MovieSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    force: bool = False,
    kometa_integration: bool = False,
) -> bool:
    should_log = True
    if entry.all_posters_uploaded:
        return False

    def get_creator_rank(creator: str | None) -> int:
        if creator and creator in priority_usernames:
            return priority_usernames.index(creator)
        return DEFAULT_CREATOR_RANK

    def find_matching_file(file_type: FileType, id_value: int) -> File | None:
        for f in set_data.files:
            if f.file_type == file_type and any(
                getattr(f, field, None) == id_value
                for field in ["show_id", "season_id", "episode_id", "collection_id", "movie_id"]
            ):
                return f
        return None

    def process_image(
        obj: Show | Season | Episode | Collection | Movie,
        file_type: FileType,
        id_value: int,
        parent: str,
        filename: str,
    ) -> None:
        nonlocal should_log
        uploaded_attr = f"{file_type.name.lower()}_uploaded"
        if getattr(obj, uploaded_attr):
            return

        file = find_matching_file(file_type=file_type, id_value=id_value)
        if not file:
            return

        image_file = get_cached_image(parent, filename)
        existing = service.cache.select(object_id=obj.id, file_type=file_type)
        if force:
            existing = None

        if existing:
            existing_rank = get_creator_rank(creator=existing.creator)
            new_rank = get_creator_rank(creator=set_data.username)
            if new_rank > existing_rank or (
                new_rank == existing_rank and set_data.id != existing.set_id
            ):
                setattr(obj, uploaded_attr, True)
                return
            if set_data.id == existing.set_id and file.last_updated <= existing.last_updated:
                setattr(obj, uploaded_attr, True)
                return

        image_file.unlink(missing_ok=True)
        if should_log:
            LOGGER.info(
                "[Mediux] Downloading '%s' by '%s'",
                set_data.set_title.replace("'", "'"),
                set_data.username,
            )
            should_log = False
        try:
            mediux.download_image(file_id=file.id, output=image_file)
        except ServiceError as err:
            LOGGER.error("[Mediux] %s", err)
            return

        if image_file.stat().st_size >= MAX_IMAGE_SIZE:
            LOGGER.warning(
                "[%s] Image file '%s' is larger than %d MB, skipping upload",
                type(service).__name__,
                image_file,
                MAX_IMAGE_SIZE,
            )
            return
        try:
            success = service.upload_image(
                object_id=obj.id, image_file=image_file, kometa_integration=kometa_integration
            )
        except ServiceError as err:
            LOGGER.error("[%s] %s", type(service).__name__, err)
            success = False
        setattr(obj, uploaded_attr, success)
        if success:
            service.cache.insert(
                object_id=obj.id,
                file_type=file_type,
                creator=set_data.username,
                set_id=set_data.id,
                last_updated=file.last_updated,
            )

    process_image(
        obj=entry,
        file_type=FileType.POSTER,
        id_value=entry.tmdb_id,
        parent=slugify(value=entry.display_name),
        filename="poster.jpg",
    )
    process_image(
        obj=entry,
        file_type=FileType.BACKDROP,
        id_value=entry.tmdb_id,
        parent=slugify(value=entry.display_name),
        filename="backdrop.jpg",
    )
    if isinstance(entry, Show) and isinstance(set_data, ShowSet):
        try:
            seasons = service.list_seasons(show_id=entry.id)
        except ServiceError as err:
            LOGGER.error("[%s] %s", type(service).__name__, err)
            seasons = []
        for season in seasons:
            entry.seasons.append(season)
            mediux_season = next(
                (x for x in set_data.show.seasons if x.number == season.number), None
            )
            if not mediux_season:
                continue
            process_image(
                obj=season,
                file_type=FileType.POSTER,
                id_value=mediux_season.id,
                parent=slugify(value=entry.display_name),
                filename=f"s{season.number:02}.jpg",
            )
            try:
                episodes = service.list_episodes(show_id=entry.id, season_id=season.id)
            except ServiceError as err:
                LOGGER.error("[%s] %s", type(service).__name__, err)
                episodes = []
            for episode in episodes:
                season.episodes.append(episode)
                mediux_episode = next(
                    (x for x in mediux_season.episodes if x.number == episode.number), None
                )
                if not mediux_episode:
                    continue
                process_image(
                    obj=episode,
                    file_type=FileType.TITLE_CARD,
                    id_value=mediux_episode.id,
                    parent=slugify(value=entry.display_name),
                    filename=f"s{season.number:02}e{episode.number:02}.jpg",
                )
    elif isinstance(entry, Collection) and isinstance(set_data, CollectionSet):
        try:
            movies = service.list_collection_movies(collection_id=entry.id)
        except ServiceError as err:
            LOGGER.error("[%s] %s", type(service).__name__, err)
            movies = []
        for movie in movies:
            entry.movies.append(movie)
            mediux_movie = next(
                (x for x in set_data.collection.movies if x.id == movie.tmdb_id), None
            )
            if not mediux_movie:
                continue
            process_image(
                obj=movie,
                file_type=FileType.POSTER,
                id_value=mediux_movie.id,
                parent=slugify(value=movie.display_name),
                filename="poster.jpg",
            )
            process_image(
                obj=movie,
                file_type=FileType.BACKDROP,
                id_value=mediux_movie.id,
                parent=slugify(value=movie.display_name),
                filename="backdrop.jpg",
            )
    return True


@app.callback(invoke_without_command=True)
def common(
    ctx: Context,
    version: Annotated[
        bool | None, Option("--version", is_eager=True, help="Show the version.")
    ] = None,
) -> None:
    if ctx.invoked_subcommand:
        return
    if version:
        CONSOLE.print(f"{__project__.title()} v{__version__}")
        raise Exit


@app.command(
    name="sync", help="Synchronize posters by fetching data from Mediux and updating your services."
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
            "Specify this option multiple times for skipping multiple libraries. ",
        ),
    ],
    start: Annotated[
        int, Option("--start", "-s", help="The starting index for processing media.")
    ] = 0,
    end: Annotated[
        int, Option("--end", "-e", help="The ending index for processing media.")
    ] = 1_000,
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
    settings, mediux, services = setup(skip_services=skip_services, clean=clean, debug=debug)

    for service_idx, service in enumerate(services):
        CONSOLE.rule(
            f"[{service_idx + 1}/{len(services)}] {type(service).__name__} Service",
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
            for idx, entry in enumerate(entries):
                CONSOLE.rule(
                    rf"[{idx + 1}/{len(entries)}] {entry.display_name} \[tmdb-{entry.tmdb_id}]",
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
                    )
                for set_data in filtered_sets:
                    if not process_set_data(
                        entry=entry,
                        set_data=set_data,
                        mediux=mediux,
                        service=service,
                        priority_usernames=settings.priority_usernames,
                        kometa_integration=settings.kometa_integration,
                    ):
                        break


@app.command(name="media", help="Manually set posters for specific Mediux media using URLs.")
def media_posters(
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
    settings, mediux, services = setup(skip_services=skip_services, clean=clean, debug=debug)

    for service_idx, service in enumerate(services):
        CONSOLE.rule(
            f"[{service_idx + 1}/{len(services)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        for idx, url in enumerate(urls):
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
            CONSOLE.rule(
                rf"[{idx + 1}/{len(urls)}] {entry.display_name} \[tmdb-{tmdb_id}]",
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
                )
            for set_data in filtered_sets:
                if not process_set_data(
                    entry=entry,
                    set_data=set_data,
                    mediux=mediux,
                    service=service,
                    priority_usernames=settings.priority_usernames,
                    kometa_integration=settings.kometa_integration,
                ):
                    break


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
    settings, mediux, services = setup(skip_services=skip_services, clean=clean, debug=debug)

    for service_idx, service in enumerate(services):
        CONSOLE.rule(
            f"[{service_idx + 1}/{len(services)}] {type(service).__name__} Service",
            align="left",
            style="title",
        )
        for idx, url in enumerate(urls):
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
            CONSOLE.rule(
                rf"[{idx + 1}/{len(urls)}] {set_data.set_title} \[tmdb-{tmdb_id}]",
                align="left",
                style="subtitle",
            )
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
            process_set_data(
                entry=entry,
                set_data=set_data,
                mediux=mediux,
                service=service,
                force=True,
                priority_usernames=settings.priority_usernames,
                kometa_integration=settings.kometa_integration,
            )


if __name__ == "__main__":
    app(prog_name=__project__)
