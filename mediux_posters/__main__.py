import logging

from typer import Typer

from mediux_posters.cli import jellyfin_app, plex_app

app = Typer()
app.add_typer(plex_app, name="plex")
app.add_typer(jellyfin_app, name="jellyfin")
LOGGER = logging.getLogger("mediux-posters")


if __name__ == "__main__":
    app(prog_name="Mediux-Posters")
