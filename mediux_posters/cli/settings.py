__all__ = ["app"]

from typer import Typer

from mediux_posters.console import CONSOLE
from mediux_posters.constants import Constants
from mediux_posters.settings import Settings

app = Typer()


@app.command(name="view", help="Display the current and default settings.")
def view() -> None:
    settings = Constants.settings()
    settings.display()


@app.command(name="locate", help="Display the path to the settings file.")
def locate() -> None:
    CONSOLE.print(Settings._file)  # noqa: SLF001
