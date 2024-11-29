import logging
from platform import python_version
from typing import Annotated

from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.services import Jellyfin
from mediux_posters.mediux import Mediux
from mediux_posters.settings import Settings
from mediux_posters.utils import delete_folder

LOGGER = logging.getLogger(__name__)
app = Typer()


def process_set(mediux: Mediux, set_data: dict, service: Jellyfin, obj: dict) -> None:
    data = mediux.process_data(data=set_data)
    if data.show:
        service.upload_show_posters(data=data.show, mediux=mediux, show_id=obj.get("Id"))
    elif data.movie:
        service.upload_movie_posters(data=data.movie, mediux=mediux, movie_id=obj.get("Id"))
    elif data.collection:
        LOGGER.warning("Uploading Collection Posters")


def update_show(service: Jellyfin, mediux: Mediux, users: list[str], tv_show: dict) -> None:
    tmdb_id = tv_show.get("ProviderIds", {}).get("Tmdb")
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, tv_show.get("Name"), tv_show.get("ProductionYear"))

    set_list = mediux.list_show_sets(tmdb_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x.get("user_created", {}).get("username") == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set.get("id", -1)))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=service, obj=tv_show)


def update_movie(service: Jellyfin, mediux: Mediux, users: list[str], movie: dict) -> None:
    tmdb_id = movie.get("ProviderIds", {}).get("Tmdb")
    if not tmdb_id:
        return
    LOGGER.info("%s | %s (%s)", tmdb_id, movie.get("Name"), movie.get("ProductionYear"))

    set_list = mediux.list_movie_sets(tmdb_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x.get("user_created", {}).get("username") == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set.get("id", -1)))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=service, obj=movie)


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

    settings = Settings.load()
    settings.save()
    if not settings.jellyfin.token:
        LOGGER.error("This command requires a Jellyfin token to be set")
        return

    jellyfin = Jellyfin(settings=settings.jellyfin)
    mediux = Mediux()
    users = ["zardooohasselfrau", "jezzfreeman", "Tiederian", "willtong93", "MiniZaki", "RuviLev"]

    if skip_shows:
        for tv_show in jellyfin.list(mediatype="tvshows"):
            update_show(service=jellyfin, mediux=mediux, users=users, tv_show=tv_show)
    if skip_movies:
        for movie in jellyfin.list(mediatype="movies"):
            update_movie(service=jellyfin, mediux=mediux, users=users, movie=movie)
