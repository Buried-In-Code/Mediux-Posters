__all__ = ["app"]

import logging
from pathlib import Path
from platform import python_version
from typing import Annotated

from plexapi.collection import Collection
from plexapi.video import Movie, Show
from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.constants import Constants
from mediux_posters.mediux import Mediux
from mediux_posters.services.plex import Plex
from mediux_posters.utils import delete_folder

LOGGER = logging.getLogger(__name__)
app = Typer()


def process_set(
    set_id: int,
    obj: Show | Movie | Collection,
    mediux: Mediux,
    plex: Plex,
    include_movies: bool = False,
) -> None:
    set_data = mediux.scrape_set(set_id=set_id)
    if not set_data:
        return
    data = mediux.process_data(data=set_data, include_movies=include_movies)
    if data.show:
        plex.upload_show_posters(data=data.show, mediux=mediux, show=obj)
    elif data.movie:
        plex.upload_movie_posters(data=data.movie, mediux=mediux, movie=obj)
    elif data.collection:
        plex.upload_collection_posters(data=data.collection, mediux=mediux, collection=obj)


def update_show(tv_show: Show, usernames: list[str], mediux: Mediux, plex: Plex) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in tv_show.guids if x.id.startswith("tmdb://")),
        None,
    )
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, tv_show.title, tv_show.year)

    if set_list := mediux.list_show_sets(tmdb_id=tmdb_id):
        if usernames:
            for username in usernames:
                user_set = next(
                    iter(
                        x for x in set_list if x.get("user_created", {}).get("username") == username
                    ),
                    None,
                )
                if not user_set:
                    continue
                process_set(
                    set_id=int(user_set.get("id", -1)), obj=tv_show, mediux=mediux, plex=plex
                )
        else:
            process_set(
                set_id=int(set_list[0].get("id", -1)), obj=tv_show, mediux=mediux, plex=plex
            )


def update_movie(movie: Movie, usernames: list[str], mediux: Mediux, plex: Plex) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in movie.guids if x.id.startswith("tmdb://")), None
    )
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, movie.title, movie.year)

    if set_list := mediux.list_movie_sets(tmdb_id=tmdb_id):
        if usernames:
            for username in usernames:
                user_set = next(
                    iter(
                        x for x in set_list if x.get("user_created", {}).get("username") == username
                    ),
                    None,
                )
                if not user_set:
                    continue
                process_set(set_id=int(user_set.get("id", -1)), obj=movie, mediux=mediux, plex=plex)
        else:
            process_set(set_id=int(set_list[0].get("id", -1)), obj=movie, mediux=mediux, plex=plex)


def update_collection(
    collection: Collection, usernames: list[str], mediux: Mediux, plex: Plex
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

    if set_list := mediux.list_collection_sets(tmdb_id=tmdb_id):
        if usernames:
            for username in usernames:
                user_set = next(
                    iter(
                        x for x in set_list if x.get("user_created", {}).get("username") == username
                    ),
                    None,
                )
                if not user_set:
                    continue
                process_set(
                    set_id=int(user_set.get("id", -1)), obj=collection, mediux=mediux, plex=plex
                )
        else:
            process_set(
                set_id=int(set_list[0].get("id", -1)), obj=collection, mediux=mediux, plex=plex
            )


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
    mediux = Constants.mediux()
    plex = Constants.plex()
    settings = Constants.settings()

    if skip_shows:
        for tv_show in plex.list(mediatype="show"):
            update_show(tv_show=tv_show, usernames=settings.usernames, mediux=mediux, plex=plex)

    if skip_movies:
        for movie in plex.list(mediatype="movie"):
            update_movie(movie=movie, usernames=settings.usernames, mediux=mediux, plex=plex)

    if skip_collections:
        for collection in plex.list(mediatype="collection"):
            update_collection(
                collection=collection, usernames=settings.usernames, mediux=mediux, plex=plex
            )


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
    mediux = Constants.mediux()
    plex = Constants.plex()

    url_list = [x.strip() for x in file.read_text().splitlines()] if file else [url]
    for entry in url_list:
        if not entry.startswith(f"{Mediux.web_url}/sets"):
            continue
        set_id = int(entry.split("/")[-1])
        set_data = mediux.scrape_set(set_id=set_id)
        if show_data := set_data.get("show"):
            if show := plex.search(tmdb_id=int(show_data["id"])):
                process_set(set_id=set_id, obj=show, mediux=mediux, plex=plex)
        elif movie_data := set_data.get("movie"):
            if movie := plex.search(tmdb_id=int(movie_data["id"])):
                process_set(set_id=set_id, obj=movie, mediux=mediux, plex=plex)
        elif collection_data := set_data.get("collection"):
            if collection := plex.search(tmdb_id=int(collection_data["id"])):
                process_set(
                    set_id=set_id, obj=collection, mediux=mediux, plex=plex, include_movies=True
                )
        else:
            LOGGER.error("Unknown data set: %s", set_data)
