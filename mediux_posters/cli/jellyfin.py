import logging
from platform import python_version
from typing import Annotated

from typer import Option, Typer

from mediux_posters import __version__, get_cache_root, setup_logging
from mediux_posters.settings import Settings
from mediux_posters.utils import delete_folder

LOGGER = logging.getLogger(__name__)
app = Typer()


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
