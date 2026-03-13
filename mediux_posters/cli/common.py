__all__ = [
    "ProcessContext",
    "ServiceOption",
    "filter_sets",
    "process_collection_data",
    "process_movie_data",
    "process_show_data",
    "setup_services",
]

import logging
from collections.abc import Generator
from dataclasses import dataclass
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
SERVICE_REGISTRY: Final[list[tuple[type, str]]] = [(Plex, "plex"), (Jellyfin, "jellyfin")]
ENTRY_FILE_MAP: Final[dict[FileType, str]] = {
    FileType.POSTER: "poster.jpg",
    FileType.BACKDROP: "backdrop.jpg",
    FileType.ALBUM: "album.jpg",
    FileType.LOGO: "logo.jpg",
}
SEASON_FILE_MAP: Final[dict[FileType, str]] = {
    FileType.POSTER: "poster.jpg",
    FileType.BACKDROP: "backdrop.jpg",
}
EPISODE_FILE_MAP: Final[dict[FileType, str]] = {
    FileType.TITLE_CARD: "titlecard.jpg",
    FileType.BACKDROP: "backdrop.jpg",
}


class ServiceOption(str, Enum):
    PLEX = Plex.__name__
    JELLYFIN = Jellyfin.__name__

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class ProcessContext:
    mediux: Mediux
    service: BaseService
    priority_usernames: list[str]
    excluded_usernames: list[str]
    force: bool = False
    kometa_integration: bool = False


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
    skip_names = {x.value for x in skip_services}
    services: list[BaseService] = []

    for cls, cfg_attr in SERVICE_REGISTRY:
        if cls.__name__ in skip_names:
            continue
        cfg = getattr(settings, cfg_attr)
        if not cfg.token:
            continue
        svc = cls(base_url=cfg.base_url, token=cfg.token, cache=cache)
        if svc.validate():
            services.append(svc)
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
                    continue
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
                if not selected:
                    raise Abort
                yield selected
                user_sets = [x for x in user_sets if x != selected]
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
    if force or not existing:
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
    if service_timestamp and service_timestamp >= existing.last_updated:
        return Action.SKIP
    return Action.UPLOAD


def process_image(  # noqa: PLR0911
    obj: Show | Season | Episode | Collection | Movie,
    cache_key: CacheKey,
    id_value: int | str,
    parent: str,
    filename: str,
    set_data: ShowSet | CollectionSet | MovieSet,
    ctx: ProcessContext,
    should_log: bool,
) -> bool:
    uploaded_attr = f"{cache_key.type.name.lower()}_uploaded"
    if getattr(obj, uploaded_attr):
        return should_log
    file = find_matching_file(set_data=set_data, file_type=cache_key.type, id_value=id_value)
    if not file:
        return should_log

    image_file = get_cached_image(parent, filename)
    existing = ctx.service.cache.select(key=cache_key)
    service_timestamp = ctx.service.cache.get_timestamp(
        key=cache_key,
        service=type(ctx.service).__name__,  # ty: ignore[invalid-argument-type]
    )

    action = determine_action(
        existing=existing,
        service_timestamp=service_timestamp,
        set_data=set_data,
        file=file,
        priority_usernames=ctx.priority_usernames,
        excluded_usernames=ctx.excluded_usernames,
        force=ctx.force,
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
            ctx.mediux.download_image(file_id=file.id, output=image_file, parent_str=parent)
        except ServiceError as err:
            LOGGER.error("[Mediux] %s", err)
            ctx.service.cache.delete(key=cache_key)
            setattr(obj, uploaded_attr, False)
            return should_log
        if not existing:
            ctx.service.cache.insert(
                key=cache_key,
                creator=set_data.username,
                set_id=set_data.id,
                last_updated=file.last_updated,
            )
        else:
            ctx.service.cache.update(
                key=cache_key,
                creator=set_data.username,
                set_id=set_data.id,
                last_updated=file.last_updated,
            )

    if image_file.stat().st_size >= MAX_IMAGE_SIZE:
        LOGGER.warning(
            "[%s] Image file '%s' is larger than %d MB, skipping upload",
            type(ctx.service).__name__,
            image_file,
            MAX_IMAGE_SIZE / 1000 / 1000,
        )
        return should_log
    if not ctx.service.upload_image(
        object_id=obj.id,
        image_file=image_file,
        file_type=cache_key.type,
        kometa_integration=ctx.kometa_integration,
    ):
        ctx.service.cache.update_service(
            key=cache_key,
            service=type(ctx.service).__name__,  # ty: ignore[invalid-argument-type]
            timestamp=None,
        )
        setattr(obj, uploaded_attr, False)
        return should_log
    ctx.service.cache.update_service(
        key=cache_key,
        service=type(ctx.service).__name__,  # ty: ignore[invalid-argument-type]
        timestamp=datetime.now(tz=timezone.utc),
    )
    setattr(obj, uploaded_attr, True)
    return should_log


def process_entry_images(
    entry: Show | Collection | Movie,
    set_data: ShowSet | CollectionSet | MovieSet,
    ctx: ProcessContext,
    should_log: bool,
) -> bool:
    parent = slugify(value=entry.display_name)
    for file_type, filename in ENTRY_FILE_MAP.items():
        should_log = process_image(
            obj=entry,
            cache_key=CacheKey(tmdb_id=entry.tmdb_id, type=file_type),
            id_value=entry.tmdb_id,
            parent=parent,
            filename=filename,
            set_data=set_data,
            ctx=ctx,
            should_log=should_log,
        )
    return should_log


def process_show_data(entry: Show, set_data: ShowSet, ctx: ProcessContext) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry, set_data=set_data, ctx=ctx, should_log=should_log
    )
    show_parent = slugify(value=entry.display_name)
    try:
        seasons = ctx.service.list_seasons(show_id=entry.id)
    except ServiceError as err:
        LOGGER.error("[%s] %s", type(ctx.service).__name__, err)
        seasons = []
    for season in seasons:
        entry.seasons.append(season)
        mediux_season = next((x for x in set_data.show.seasons if x.number == season.number), None)
        if not mediux_season:
            continue
        season_parent = show_parent + f"/S{season.number:02}"
        for file_type, filename in SEASON_FILE_MAP.items():
            should_log = process_image(
                obj=season,
                cache_key=CacheKey(tmdb_id=entry.tmdb_id, season_num=season.number, type=file_type),
                id_value=mediux_season.id,
                parent=season_parent,
                filename=filename,
                set_data=set_data,
                ctx=ctx,
                should_log=should_log,
            )
        try:
            episodes = ctx.service.list_episodes(show_id=entry.id, season_id=season.id)
        except ServiceError as err:
            LOGGER.error("[%s] %s", type(ctx.service).__name__, err)
            episodes = []
        for episode in episodes:
            season.episodes.append(episode)
            mediux_episode = next(
                (x for x in mediux_season.episodes if x.number == episode.number), None
            )
            if not mediux_episode:
                continue
            episode_parent = season_parent + f"/E{episode.number:02}"
            for file_type, filename in EPISODE_FILE_MAP.items():
                should_log = process_image(
                    obj=episode,
                    cache_key=CacheKey(
                        tmdb_id=entry.tmdb_id,
                        season_num=season.number,
                        episode_num=episode.number,
                        type=file_type,
                    ),
                    id_value=mediux_episode.id,
                    parent=episode_parent,
                    filename=filename,
                    set_data=set_data,
                    ctx=ctx,
                    should_log=should_log,
                )


def process_collection_data(
    entry: Collection, set_data: CollectionSet, ctx: ProcessContext
) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry, set_data=set_data, ctx=ctx, should_log=should_log
    )
    try:
        movies = ctx.service.list_collection_movies(collection_id=entry.id)
    except ServiceError as err:
        LOGGER.error("[%s] %s", type(ctx.service).__name__, err)
        movies = []
    for movie in movies:
        entry.movies.append(movie)
        mediux_movie = next((x for x in set_data.collection.movies if x.id == movie.tmdb_id), None)
        if not mediux_movie:
            continue
        parent = slugify(value=movie.display_name)
        for file_type, filename in ENTRY_FILE_MAP.items():
            should_log = process_image(
                obj=movie,
                cache_key=CacheKey(tmdb_id=movie.tmdb_id, type=file_type),
                id_value=mediux_movie.id,
                parent=parent,
                filename=filename,
                set_data=set_data,
                ctx=ctx,
                should_log=should_log,
            )


def process_movie_data(entry: Movie, set_data: MovieSet, ctx: ProcessContext) -> None:
    should_log = True
    should_log = process_entry_images(
        entry=entry, set_data=set_data, ctx=ctx, should_log=should_log
    )
