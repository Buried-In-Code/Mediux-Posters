import logging
from pathlib import Path
from platform import python_version
from typing import Annotated

from plexapi.collection import Collection
from plexapi.exceptions import Unauthorized
from plexapi.video import Movie, Show
from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.mediux import Mediux
from mediux_posters.services.plex import Plex
from mediux_posters.settings import Settings
from mediux_posters.utils import delete_folder

LOGGER = logging.getLogger(__name__)
app = Typer()


def process_set(
    mediux: Mediux, set_data: dict, service: Plex, obj: Show | Movie | Collection
) -> None:
    data = mediux.process_data(data=set_data)
    if data.show:
        service.upload_show_posters(data=data.show, mediux=mediux, show=obj)
    elif data.movie:
        service.upload_movie_posters(data=data.movie, mediux=mediux, movie=obj)
    elif data.collection:
        service.upload_collection_posters(data=data.collection, mediux=mediux, collection=obj)


def update_show(service: Plex, mediux: Mediux, users: list[str], tv_show: Show) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in tv_show.guids if x.id.startswith("tmdb://")),
        None,
    )
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, tv_show.title, tv_show.year)

    set_list = mediux.list_show_sets(tmdb_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x["user_created"]["username"] == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set["id"]))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=service, obj=tv_show)


def update_movie(service: Plex, mediux: Mediux, users: list[str], movie: Movie) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in movie.guids if x.id.startswith("tmdb://")), None
    )
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, movie.title, movie.year)

    set_list = mediux.list_movie_sets(tmdb_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x["user_created"]["username"] == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set["id"]))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=service, obj=movie)


def update_collection(
    service: Plex, mediux: Mediux, users: list[str], collection: Collection
) -> None:
    tmdb_id = next(
        iter(
            x.tag.lower().removeprefix("tmdb-")
            for x in collection.labels
            if x.tag.lower().startswith("tmdb-")
        ),
        None,
    )
    if not tmdb_id:
        return
    LOGGER.info("%s | %s", tmdb_id, collection.title)

    set_list = mediux.list_collection_sets(tmdb_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x["user_created"]["username"] == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set["id"]))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=service, obj=collection)


@app.command()
def sync(
    skip_shows: Annotated[bool, Option("--skip-shows", show_default=False)] = True,
    skip_movies: Annotated[bool, Option("--skip-movies", show_default=False)] = True,
    skip_collections: Annotated[bool, Option("--skip-collections", show_default=False)] = True,
    clean_cache: Annotated[bool, Option("--clean", show_default=False)] = False,
    debug: Annotated[
        bool, Option("--debug", help="Enable debug mode to show extra information.")
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())

    settings = Settings.load()
    settings.save()
    if not settings.plex.token:
        LOGGER.error("This command requires a Plex Token to be set")
        return

    try:
        plex = Plex(settings=settings.plex)
    except Unauthorized as err:
        LOGGER.error(err)
        return
    mediux = Mediux()
    users = ["zardooohasselfrau", "jezzfreeman", "Tiederian", "willtong93", "MiniZaki", "RuviLev"]

    if skip_shows:
        for tv_show in plex.list(mediatype="show"):
            update_show(service=plex, mediux=mediux, users=users, tv_show=tv_show)

    if skip_movies:
        for movie in plex.list(mediatype="movie"):
            update_movie(service=plex, mediux=mediux, users=users, movie=movie)

    if skip_collections:
        for collection in plex.list(mediatype="collection"):
            update_collection(service=plex, mediux=mediux, users=users, collection=collection)


@app.command(name="set")
def set_posters(
    file: Annotated[Path | None, Option(dir_okay=False, exists=True, show_default=False)] = None,
    url: Annotated[str | None, Option(show_default=False)] = None,
    clean_cache: Annotated[bool, Option("--clean", show_default=False)] = False,
    debug: Annotated[
        bool, Option("--debug", help="Enable debug mode to show extra information.")
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())

    settings = Settings.load()
    settings.save()
    if not settings.plex.token:
        LOGGER.error("This command requires a Plex Token to be set")
        return
    try:
        plex = Plex(settings=settings.plex)
    except Unauthorized as err:
        LOGGER.error(err)
        return

    mediux = Mediux()

    url_list = [x.strip() for x in file.read_text().splitlines()] if file else [url]
    for entry in url_list:
        if not entry.startswith(f"{Mediux.web_url}/sets"):
            continue
        set_id = entry.split("/")[-1]
        set_data = mediux.scrape_set(set_id=set_id)
        if show_data := set_data.get("show"):
            tmdb_id = int(show_data["id"])
            if show := plex.search(tmdb_id=tmdb_id):
                process_set(mediux=mediux, set_data=set_data, service=plex, obj=show)
        elif movie_data := set_data.get("movie"):
            tmdb_id = int(movie_data["id"])
            if movie := plex.search(tmdb_id=tmdb_id):
                process_set(mediux=mediux, set_data=set_data, service=plex, obj=movie)
        elif collection_data := set_data.get("collection"):
            tmdb_id = int(collection_data["id"])
            if collection := plex.search(tmdb_id=tmdb_id):
                process_set(mediux=mediux, set_data=set_data, service=plex, obj=collection)
            movie_ids = [x["id"] for x in collection_data["movies"]]
            for movie_id in movie_ids:
                if movie := plex.search(tmdb_id=movie_id):
                    process_set(mediux=mediux, set_data=set_data, service=plex, obj=movie)
        else:
            LOGGER.error("Unknown data set: %s", set_data)
