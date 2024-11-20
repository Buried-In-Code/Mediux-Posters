import logging
from pathlib import Path
from platform import python_version
from typing import Annotated

from plexapi.exceptions import Unauthorized
from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.jellyfin import Jellyfin
from mediux_posters.mediux import Mediux
from mediux_posters.new.cli import app as new_app
from mediux_posters.plex import Plex
from mediux_posters.settings import Settings
from mediux_posters.utils import delete_folder

app = Typer()
app.add_typer(new_app, name="new")
LOGGER = logging.getLogger("mediux-posters")


def read_urls(target: Path | None) -> list[str]:
    if target:
        return [
            x.strip()
            for x in target.read_text().splitlines()
            if x.strip().startswith("https://mediux.pro/sets")
            or x.strip().startswith("https://mediux.pro/boxsets")
        ]
    return []


def lookup_set(set_data: dict, mediux: Mediux, services: list[Jellyfin | Plex]) -> None:
    data = mediux.process_data(data=set_data)
    for service in services:
        if data.show:
            service.lookup_show(show=data.show, mediux=mediux)
        elif data.movie:
            service.lookup_movie(movie=data.movie, mediux=mediux)
        elif data.collection:
            service.lookup_collection(collection=data.collection, mediux=mediux)


@app.command()
def artist(
    file: Annotated[Path | None, Option(dir_okay=False, exists=True, show_default=False)] = None,
    username: Annotated[str | None, Option(show_default=False)] = None,
    clean_cache: Annotated[bool, Option("--clean", show_default=False)] = False,
    debug: Annotated[
        bool, Option("--debug", help="Enable debug mode to show extra information.")
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Jellyfin Mediux Posters v%s", __version__)

    settings = Settings.load()
    settings.save()

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())

    mediux = Mediux()
    services = []
    if settings.jellyfin.api_key:
        services.append(Jellyfin(settings=settings.jellyfin))
    if settings.plex.token:
        try:
            services.append(Plex(settings=settings.plex))
        except Unauthorized as err:
            LOGGER.error(err)
    usernames = [x.strip() for x in file.read_text().splitlines()] if file else [username]
    for entry in usernames:
        results = []
        page = 1
        artist_data = mediux.scrape_artist(username=entry, page=page)
        while len(artist_data) >= 1:
            results.extend(artist_data)
            page += 1
            artist_data = mediux.scrape_artist(username=entry, page=page)
        for set_id in [x["id"] for x in results]:
            if set_data := mediux.scrape_set(set_id=set_id):
                lookup_set(set_data=set_data, mediux=mediux, services=services)


@app.command()
def main(
    file: Annotated[Path | None, Option(dir_okay=False, exists=True, show_default=False)] = None,
    url: Annotated[str | None, Option(show_default=False)] = None,
    clean_cache: Annotated[bool, Option("--clean", show_default=False)] = False,
    debug: Annotated[
        bool, Option("--debug", help="Enable debug mode to show extra information.")
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Jellyfin Mediux Posters v%s", __version__)

    settings = Settings.load()
    settings.save()

    if clean_cache:
        LOGGER.info("Cleaning Cache")
        delete_folder(folder=get_cache_root())

    mediux = Mediux()
    services = []
    if settings.jellyfin.api_key:
        services.append(Jellyfin(settings=settings.jellyfin))
    if settings.plex.token:
        try:
            services.append(Plex(settings=settings.plex))
        except Unauthorized as err:
            LOGGER.error(err)
    url_list = read_urls(target=file)
    if url and (
        url.strip().startswith("https://mediux.pro/sets")
        or url.strip().startswith("https://mediux.pro/boxsets")
    ):
        url_list.append(url.strip())
    for entry in url_list:
        if entry.strip().startswith("https://mediux.pro/sets"):
            if set_data := mediux.scrape_set(set_url=entry):
                lookup_set(set_data=set_data, mediux=mediux, services=services)
        elif entry.strip().startswith("https://mediux.pro/boxsets"):
            boxset_data = mediux.scrape_boxset(boxset_url=entry)
            for set_data in boxset_data.get("sets", []):
                lookup_set(set_data=set_data, mediux=mediux, services=services)


if __name__ == "__main__":
    main()
