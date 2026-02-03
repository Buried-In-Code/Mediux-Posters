__all__ = ["app"]

from typing import Annotated

from typer import Context, Exit, Option, Typer

from mediux_posters import __version__
from mediux_posters.console import CONSOLE

app = Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def common(
    ctx: Context,
    version: Annotated[
        bool | None, Option("--version", is_eager=True, help="Show the version and exit.")
    ] = None,
) -> None:
    if ctx.invoked_subcommand:
        return
    if version:
        CONSOLE.print(f"Mediux Posters v{__version__}")
        raise Exit
