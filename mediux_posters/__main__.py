import logging
from pathlib import Path
from platform import python_version
from typing import Annotated

from typer import Option, Typer

from mediux_posters import __version__, setup_logging
from mediux_posters.jellyfin import Jellyfin
from mediux_posters.mediux import Mediux
from mediux_posters.plex import Plex
from mediux_posters.settings import Settings

app = Typer()
LOGGER = logging.getLogger("mediux-posters")


def read_urls(target: Path | None) -> list[str]:
    if target:
        return [
            x.strip()
            for x in target.read_text().splitlines()
            if x.strip().startswith("https://mediux.pro/sets")
        ]
    return []


@app.command()
def main(
    file: Annotated[Path | None, Option(dir_okay=False, exists=True, show_default=False)] = None,
    url: Annotated[str | None, Option(show_default=False)] = None,
    debug: Annotated[
        bool, Option("--debug", help="Enable debug mode to show extra information.")
    ] = False,
) -> None:
    setup_logging(debug=debug)
    LOGGER.info("Python v%s", python_version())
    LOGGER.info("Jellyfin Mediux Posters v%s", __version__)

    settings = Settings.load()
    settings.save()

    mediux = Mediux()
    services = []
    if settings.jellyfin.api_key:
        services.append(Jellyfin(settings=settings.jellyfin))
    if settings.plex.token:
        services.append(Plex(settings=settings.plex))
    url_list = read_urls(target=file)
    if url and url.strip().startswith("https://mediux.pro/sets"):
        url_list.append(url.strip())
    for entry in url_list:
        set_data = mediux.scrape_set(set_url=entry)
        if not set_data:
            continue
        data = mediux.process_data(data=set_data)
        for service in services:
            if data.show:
                service.lookup_show(show=data.show, mediux=mediux)
            elif data.movie:
                service.lookup_movie(movie=data.movie, mediux=mediux)
            elif data.collection:
                service.lookup_collection(collection=data.collection, mediux=mediux)


if __name__ == "__main__":
    main()
