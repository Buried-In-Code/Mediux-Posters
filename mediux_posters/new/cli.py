import logging
from platform import python_version

from plexapi.exceptions import Unauthorized
from plexapi.video import Movie, Show
from typer import Typer

from mediux_posters import __version__, setup_logging
from mediux_posters.new.mediux import Mediux
from mediux_posters.new.plex import Plex
from mediux_posters.settings import Settings

LOGGER = logging.getLogger(__name__)
app = Typer()


def process_set(mediux: Mediux, set_data: dict, service: Plex, obj: Show | Movie) -> None:
    data = mediux.process_data(data=set_data)
    if data.show:
        service.upload_show_posters(data=data.show, mediux=mediux, show=obj)
    elif data.movie:
        service.upload_movie_posters(data=data.movie, mediux=mediux, movie=obj)
    elif data.collection:
        service.upload_collection_posters(data=data.collection, mediux=mediux, collection=obj)


def update_plex_show(plex: Plex, mediux: Mediux, users: list[str], tv_show: Show) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in tv_show.guids if x.id.startswith("tmdb://")),
        None,
    )
    if not tmdb_id:
        return
    LOGGER.info(f"{tmdb_id} | {tv_show.title} ({tv_show.year})")

    set_list = mediux.list_show_sets(show_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x["user_created"]["username"] == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set["id"]))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=plex, obj=tv_show)


def update_plex_movie(plex: Plex, mediux: Mediux, users: list[str], movie: Movie) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in movie.guids if x.id.startswith("tmdb://")), None
    )
    if not tmdb_id:
        return
    LOGGER.info(f"{tmdb_id} | {movie.title} ({movie.year})")

    set_list = mediux.list_movie_sets(movie_id=tmdb_id)
    for username in users:
        user_set = next(
            iter(x for x in set_list if x["user_created"]["username"] == username), None
        )
        if not user_set:
            continue
        set_data = mediux.scrape_set(set_id=int(user_set["id"]))
        if not set_data:
            continue
        process_set(mediux=mediux, set_data=set_data, service=plex, obj=movie)


def update_plex_collection(
    plex: Plex, mediux: Mediux, users: list[str], collection: Collection
) -> None:
    tmdb_id = next(
        iter(x.id.removeprefix("tmdb://") for x in collection.guids if x.id.startswith("tmdb://")),
        None,
    )
    if not tmdb_id:
        return
    LOGGER.info(f"{tmdb_id} | {collection.title}")


@app.command()
def plex() -> None:
    setup_logging(debug=False)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Mediux Posters v%s", __version__)

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

    for tv_show in plex.list(mediatype="show"):
        update_plex_show(plex=plex, mediux=mediux, users=users, tv_show=tv_show)

    for movie in plex.list(mediatype="movie"):
        update_plex_movie(plex=plex, mediux=mediux, users=users, movie=movie)

    for collection in plex.list(mediatype="collection"):
        update_plex_collection(plex=plex, mediux=mediux, users=users, collection=collection)
