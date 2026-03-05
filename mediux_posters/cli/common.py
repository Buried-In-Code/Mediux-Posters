__all__ = [
    "ServiceOption",
    "filter_sets",
    "process_collection_data",
    "process_movie_data",
    "process_show_data",
    "setup_services",
]

import logging
from collections.abc import Generator
from datetime import datetime, timezone
from enum import Enum
from platform import python_version
from typing import Final, Protocol, TypeVar

from prompt_toolkit.styles import Style
from questionary import Choice, select
from typer import Abort

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
from mediux_posters.services.service_cache import CacheData, CacheKey, ServiceCache
from mediux_posters.settings import Settings
from mediux_posters.utils import delete_folder, get_cached_image, slugify

LOGGER = logging.getLogger(__name__)
DEFAULT_CREATOR_RANK: Final[int] = 1_000_000
MAX_IMAGE_SIZE: Final[int] = 10_000_000  # 10 MB


class ServiceOption(str, Enum):
    PLEX = Plex.__name__
    JELLYFIN = Jellyfin.__name__

    def __str__(self) -> str:
        return self.value


class Action(str, Enum):
    SKIP = "Skip"
    DOWNLOAD = "Download"
    UPLOAD = "Upload"

    def __str__(self) -> str:
        return self.value


def setup_services(
    skip_services: list[ServiceOption], clean: bool, debug: bool = False
) -> tuple[Settings, Mediux, list[BaseService]]:
    setup_logging(debug=debug)
    LOGGER.info("Mediux Posters v%s", __version__)
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

    cache = ServiceCache()
    services = []
    skip_services = [x.value for x in skip_services]
    if Plex.__name__ not in skip_services and settings.plex.token:
        plex = Plex(base_url=settings.plex.base_url, token=settings.plex.token, cache=cache)
        if plex.validate():
            services.append(plex)
    if Jellyfin.__name__ not in skip_services and settings.jellyfin.token:
        jellyfin = Jellyfin(
            base_url=settings.jellyfin.base_url, token=settings.jellyfin.token, cache=cache
        )
        if jellyfin.validate():
            services.append(jellyfin)
    if not services:
        LOGGER.error("No services configured, check your settings")
        raise Abort

    return settings, mediux, services


T = TypeVar("T", bound="MediuxSet")


class MediuxSet(Protocol):
    id: int
    set_title: str
    username: str


def filter_sets(
    set_list: list[T],
    priority_usernames: list[str],
    only_priority_usernames: bool,
    interactive: bool = False,
) -> Generator[T]:
    if not set_list:
        return
    for username in priority_usernames:
        if interactive:
            user_sets = [x for x in set_list if x.username == username]
            if not user_sets:
                continue
            while user_sets:
                if len(user_sets) == 1:
                    yield user_sets.pop(0)
                else:
                    choices = [
                        Choice(
                            title=[("class:dim", f"{x.id} | "), ("class:title", x.set_title)],
                            description=f"{Mediux.WEB_URL}/sets/{x.id}",
                            value=x,
                        )
                        for x in user_sets
                    ]
                    selected = select(
                        f"Multiple sets found from '{username}'",
                        choices=choices,
                        style=Style([("dim", "dim")]),
                    ).ask()
                    if selected:
                        yield selected
                        user_sets = [x for x in user_sets if x != selected]
                    else:
                        raise Abort
        else:
            yield from [x for x in set_list if x.username == username]
    if not only_priority_usernames:
        yield from [x for x in set_list if x.username not in priority_usernames]


def get_creator_rank(
    priority_usernames: list[str], excluded_usernames: list[str], creator: str | None
) -> int:
    if creator and creator in priority_usernames:
        return priority_usernames.index(creator)
    if creator and creator in excluded_usernames:
        return DEFAULT_CREATOR_RANK * 2
    return DEFAULT_CREATOR_RANK


def find_matching_file(
    set_data: ShowSet | CollectionSet | MovieSet, file_type: FileType, id_value: int | str
) -> File | None:
    for f in set_data.files:
        if f.file_type == file_type and any(
            getattr(f, field, None) == id_value
            for field in ["show_id", "season_id", "episode_id", "collection_id", "movie_id"]
        ):
            return f
    return None


def determine_action(  # noqa: PLR0911
    existing: CacheData | None,
    service_timestamp: datetime | None,
    set_data: ShowSet | CollectionSet | MovieSet,
    file: File,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    force: bool,
) -> Action:
    if force:
        return Action.DOWNLOAD
    if not existing:
        return Action.DOWNLOAD

    existing_rank = get_creator_rank(
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        creator=existing.creator,
    )
    new_rank = get_creator_rank(
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        creator=set_data.username,
    )

    if new_rank > existing_rank:
        return Action.SKIP
    if new_rank < existing_rank:
        return Action.DOWNLOAD
    if existing.set_id != set_data.id:
        return Action.SKIP
    if file.last_updated > existing.last_updated:
        return Action.DOWNLOAD
    if service_timestamp is None or service_timestamp < existing.last_updated:
        return Action.UPLOAD
    return Action.SKIP


def process_image(  # noqa: PLR0911
    obj: Show | Season | Episode | Collection | Movie,
    cache_key: CacheKey,
    id_value: int | str,
    parent: str,
    filename: str,
    set_data: ShowSet | CollectionSet | MovieSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    should_log: bool,
    kometa_integration: bool = False,
    force: bool = False,
) -> bool:
    uploaded_attr = f"{cache_key.type.name.lower()}_uploaded"
    if getattr(obj, uploaded_attr):
        return should_log
    file = find_matching_file(set_data=set_data, file_type=cache_key.type, id_value=id_value)
    if not file:
        return should_log

    image_file = get_cached_image(parent, filename)
    existing = service.cache.select(key=cache_key)
    service_timestamp = service.cache.get_timestamp(key=cache_key, service=type(service).__name__)

    action = determine_action(
        existing=existing,
        service_timestamp=service_timestamp,
        set_data=set_data,
        file=file,
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        force=force,
    )
    if action is Action.SKIP:
        return should_log
    if should_log:
        LOGGER.info(
            "[Mediux] %sing '%s' by '%s'",
            action,
            set_data.set_title.replace("'", "'"),
            set_data.username,
        )
        should_log = False
    if action is Action.DOWNLOAD or not image_file.exists():
        image_file.unlink(missing_ok=True)
        try:
            mediux.download_image(file_id=file.id, output=image_file)
        except ServiceError as err:
            LOGGER.error("[Mediux] %s", err)
            service.cache.delete(key=cache_key)
            setattr(obj, uploaded_attr, False)
            return should_log
        if not existing:
            service.cache.insert(
                key=cache_key,
                creator=set_data.username,
                set_id=set_data.id,
                last_updated=file.last_updated,
            )
        else:
            service.cache.update(
                key=cache_key,
                creator=set_data.username,
                set_id=set_data.id,
                last_updated=file.last_updated,
            )

    if image_file.stat().st_size >= MAX_IMAGE_SIZE:
        LOGGER.warning(
            "[%s] Image file '%s' is larger than %d MB, skipping upload",
            type(service).__name__,
            image_file,
            MAX_IMAGE_SIZE / 1000 / 1000,
        )
        return should_log
    if not service.upload_image(
        object_id=obj.id, image_file=image_file, kometa_integration=kometa_integration
    ):
        service.cache.update_service(key=cache_key, service=type(service).__name__, timestamp=None)
        setattr(obj, uploaded_attr, False)
        return should_log
    now = datetime.now(tz=timezone.utc)
    service.cache.update_service(key=cache_key, service=type(service).__name__, timestamp=now)
    setattr(obj, uploaded_attr, True)
    return should_log


def process_entry_images(
    entry: Show | Collection | Movie,
    set_data: ShowSet | CollectionSet | MovieSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    should_log: bool,
    kometa_integration: bool = False,
    force: bool = False,
) -> bool:
    parent = slugify(value=entry.display_name)
    file_map = {FileType.POSTER: "poster.jpg", FileType.BACKDROP: "backdrop.jpg"}
    for file_type, filename in file_map.items():
        should_log = process_image(
            obj=entry,
            cache_key=CacheKey(tmdb_id=entry.tmdb_id, type=file_type),
            id_value=entry.tmdb_id,
            parent=parent,
            filename=filename,
            set_data=set_data,
            mediux=mediux,
            service=service,
            priority_usernames=priority_usernames,
            excluded_usernames=excluded_usernames,
            kometa_integration=kometa_integration,
            force=force,
            should_log=should_log,
        )
    return should_log


def process_show_data(
    entry: Show,
    set_data: ShowSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    force: bool = False,
    kometa_integration: bool = False,
) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry,
        set_data=set_data,
        mediux=mediux,
        service=service,
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        kometa_integration=kometa_integration,
        force=force,
        should_log=should_log,
    )
    try:
        seasons = service.list_seasons(show_id=entry.id)
    except ServiceError as err:
        LOGGER.error("[%s] %s", type(service).__name__, err)
        seasons = []
    for season in seasons:
        entry.seasons.append(season)
        mediux_season = next((x for x in set_data.show.seasons if x.number == season.number), None)
        if not mediux_season:
            continue
        should_log = process_image(
            obj=season,
            cache_key=CacheKey(
                tmdb_id=entry.tmdb_id, season_num=season.number, type=FileType.POSTER
            ),
            id_value=mediux_season.id,
            parent=slugify(value=entry.display_name),
            filename=f"s{season.number:02}.jpg",
            set_data=set_data,
            mediux=mediux,
            service=service,
            priority_usernames=priority_usernames,
            excluded_usernames=excluded_usernames,
            kometa_integration=kometa_integration,
            force=force,
            should_log=should_log,
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
            should_log = process_image(
                obj=episode,
                cache_key=CacheKey(
                    tmdb_id=entry.tmdb_id,
                    season_num=season.number,
                    episode_num=episode.number,
                    type=FileType.TITLE_CARD,
                ),
                id_value=mediux_episode.id,
                parent=slugify(value=entry.display_name),
                filename=f"s{season.number:02}e{episode.number:02}.jpg",
                set_data=set_data,
                mediux=mediux,
                service=service,
                priority_usernames=priority_usernames,
                excluded_usernames=excluded_usernames,
                kometa_integration=kometa_integration,
                force=force,
                should_log=should_log,
            )


def process_collection_data(
    entry: Collection,
    set_data: CollectionSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    force: bool = False,
    kometa_integration: bool = False,
) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry,
        set_data=set_data,
        mediux=mediux,
        service=service,
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        kometa_integration=kometa_integration,
        force=force,
        should_log=should_log,
    )
    try:
        movies = service.list_collection_movies(collection_id=entry.id)
    except ServiceError as err:
        LOGGER.error("[%s] %s", type(service).__name__, err)
        movies = []
    for movie in movies:
        entry.movies.append(movie)
        mediux_movie = next((x for x in set_data.collection.movies if x.id == movie.tmdb_id), None)
        if not mediux_movie:
            continue
        parent = slugify(value=movie.display_name)
        file_map = {FileType.POSTER: "poster.jpg", FileType.BACKDROP: "backdrop.jpg"}
        for file_type, filename in file_map.items():
            should_log = process_image(
                obj=movie,
                cache_key=CacheKey(tmdb_id=movie.tmdb_id, type=file_type),
                id_value=mediux_movie.id,
                parent=parent,
                filename=filename,
                set_data=set_data,
                mediux=mediux,
                service=service,
                priority_usernames=priority_usernames,
                excluded_usernames=excluded_usernames,
                kometa_integration=kometa_integration,
                force=force,
                should_log=should_log,
            )


def process_movie_data(
    entry: Movie,
    set_data: MovieSet,
    mediux: Mediux,
    service: BaseService,
    priority_usernames: list[str],
    excluded_usernames: list[str],
    force: bool = False,
    kometa_integration: bool = False,
) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry,
        set_data=set_data,
        mediux=mediux,
        service=service,
        priority_usernames=priority_usernames,
        excluded_usernames=excluded_usernames,
        kometa_integration=kometa_integration,
        force=force,
        should_log=should_log,
    )
