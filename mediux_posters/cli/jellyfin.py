__all__ = ["app"]

import logging
from platform import python_version
from typing import Annotated

from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.constants import Constants
from mediux_posters.mediux import Mediux
from mediux_posters.services import Jellyfin
from mediux_posters.utils import delete_folder

LOGGER = logging.getLogger(__name__)
app = Typer()


def process_set(set_id: int, obj: dict, mediux: Mediux, jellyfin: Jellyfin) -> None:
    set_data = mediux.scrape_set(set_id=set_id)
    if not set_data:
        return
    data = mediux.process_data(data=set_data)
    if data.show:
        jellyfin.upload_show_posters(data=data.show, mediux=mediux, show_id=obj.get("Id"))
    elif data.movie:
        jellyfin.upload_movie_posters(data=data.movie, mediux=mediux, movie_id=obj.get("Id"))
    elif data.collection:
        LOGGER.warning("NotYetImplemented: Uploading Collection Posters")


def update_show(tv_show: dict, usernames: list[str], mediux: Mediux, jellyfin: Jellyfin) -> None:
    tmdb_id = tv_show.get("ProviderIds", {}).get("Tmdb")
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, tv_show.get("Name"), tv_show.get("ProductionYear"))

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
                    set_id=int(user_set.get("id", -1)),
                    obj=tv_show,
                    mediux=mediux,
                    jellyfin=jellyfin,
                )
        else:
            process_set(
                set_id=int(set_list[0].get("id", -1)), obj=tv_show, mediux=mediux, jellyfin=jellyfin
            )


def update_movie(movie: dict, usernames: list[str], mediux: Mediux, jellyfin: Jellyfin) -> None:
    tmdb_id = movie.get("ProviderIds", {}).get("Tmdb")
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, movie.get("Name"), movie.get("ProductionYear"))

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
                process_set(
                    set_id=int(user_set.get("id", -1)), obj=movie, mediux=mediux, jellyfin=jellyfin
                )
        else:
            process_set(
                set_id=int(set_list[0].get("id", -1)), obj=movie, mediux=mediux, jellyfin=jellyfin
            )


@app.command()
def sync(
    skip_shows: Annotated[bool, Option("--skip-shows", show_default=False)] = True,
    skip_movies: Annotated[bool, Option("--skip-movies", show_default=False)] = True,
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
    jellyfin = Constants.jellyfin()
    mediux = Constants.mediux()
    settings = Constants.settings()

    if skip_shows:
        for tv_show in jellyfin.list(mediatype="tvshows"):
            update_show(
                tv_show=tv_show, usernames=settings.usernames, mediux=mediux, jellyfin=jellyfin
            )
    if skip_movies:
        for movie in jellyfin.list(mediatype="movies"):
            update_movie(
                movie=movie, usernames=settings.usernames, mediux=mediux, jellyfin=jellyfin
            )
