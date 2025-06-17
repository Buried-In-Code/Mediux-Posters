__all__ = ["app"]

from typer import Typer

from visage.console import CONSOLE
from visage.settings import Settings

app = Typer(help="Commands for application settings.")


@app.command(name="view", help="Display the current and default settings.")
def view_settings() -> None:
    settings = Settings.load()
    settings.display()


@app.command(name="locate", help="Display the path to the settings file.")
def locate_settings() -> None:
    CONSOLE.print(Settings._file)  # noqa: SLF001
