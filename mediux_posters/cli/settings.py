__all__ = ["settings"]

from mediux_posters.cli._typer import app
from mediux_posters.settings import Settings


@app.command(help="Display app settings and defaults.")
def settings() -> None:
    settings = Settings.load()
    settings.display()
