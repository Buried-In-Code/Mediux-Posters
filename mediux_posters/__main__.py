import json
import logging
from json import JSONDecodeError
from pathlib import Path
from platform import python_version
from typing import Annotated

from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.jellyfin import Jellyfin
from mediux_posters.mediux import Mediux
from mediux_posters.plex import Plex
from mediux_posters.settings import Settings

app = Typer()
LOGGER = logging.getLogger("mediux-posters")


def read_set_urls(target: Path | None) -> list[str]:
    if target:
        return [
            x for x in target.read_text().splitlines() if x.startswith("https://mediux.pro/sets")
        ]
    return []


@app.command()
def main(
    sets_file: Annotated[
        Path | None, Option("--sets-file", dir_okay=False, exists=True, show_default=False)
    ] = None,
    set_url: Annotated[str | None, Option("--set-url", show_default=False)] = None,
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
    jellyfin = None
    if settings.jellyfin.api_key:
        jellyfin = Jellyfin(settings=settings.jellyfin)
    plex = None
    if settings.plex.token:
        plex = Plex(settings=settings.plex)
    set_list = read_set_urls(target=sets_file)
    if set_url:
        set_list.append(set_url)
    for set_url in set_list:  # noqa: PLR1704
        cache_file = get_cache_root() / "sets" / f"{set_url.split('/')[-1]}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        if cache_file.exists():
            try:
                with cache_file.open("r") as stream:
                    set_data = json.load(stream)
            except JSONDecodeError:
                set_data = mediux.scrape_set(set_url=set_url)
        else:
            set_data = mediux.scrape_set(set_url=set_url)
        if set_data:
            with cache_file.open("w") as stream:
                json.dump(set_data, stream, ensure_ascii=True, indent=4)
            data = mediux.process_data(data=set_data)
            if data.show:
                mediux.download_set_images(data=data)
                if jellyfin:
                    jellyfin.update_series_set(show=data.show)
                if plex:
                    plex.update_series_set(show=data.show)
            elif data.movies:
                if data.poster_id or data.backdrop_id:
                    mediux.download_collection_images(folder_name=data.name, data=data)
                    if jellyfin:
                        jellyfin.update_collection(folder_name=data.name, collection_name=data.name)
                    if plex:
                        plex.update_collection(folder_name=data.name, collection_name=data.name)
                for movie in data.movies:
                    mediux.download_movie_image(folder_name=data.name, movie=movie)
                    if jellyfin:
                        jellyfin.update_movie(folder_name=data.name, movie=movie)
                    if plex:
                        plex.update_movie(folder_name=data.name, movie=movie)


if __name__ == "__main__":
    main()
