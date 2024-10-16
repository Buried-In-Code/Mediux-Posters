__all__ = ["find_poster", "create_menu"]

import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.theme import Theme

from mediux_posters import get_project_root

CONSOLE = Console(
    theme=Theme(
        {
            "prompt": "green",
            "prompt.border": "dim green",
            "prompt.choices": "white",
            "prompt.default": "dim white",
            "title": "magenta",
            "title.border": "dim magenta",
            "subtitle": "blue",
            "subtitle.border": "dim blue",
            "syntax.border": "dim cyan",
            "logging.level.debug": "dim white",
            "logging.level.info": "white",
            "logging.level.warning": "yellow",
            "logging.level.error": "bold red",
            "logging.level.critical": "bold magenta",
        }
    )
)
LOGGER = logging.getLogger(__name__)


def find_poster(mediatype: str, folder: str, filename: str) -> Path | None:
    cover_folder = get_project_root() / "covers" / mediatype / folder
    poster_path = cover_folder / f"{filename}.jpg"
    if poster_path.exists():
        return poster_path
    return None


def create_menu(
    options: list[str],
    title: str | None = None,
    subtitle: str | None = None,
    prompt: str = "Select",
    default: str | None = None,
) -> int | None:
    if not options:
        return 0
    if len(options) == 1:
        return 1
    panel_text = []
    for index, item in enumerate(options):
        panel_text.append(f"[prompt]{index + 1}:[/] [prompt.choices]{item}[/]")
    if default:
        panel_text.append(f"[prompt]0:[/] [prompt.default]{default}[/]")
    CONSOLE.print(
        Panel("\n".join(panel_text), border_style="prompt.border", title=title, subtitle=subtitle)
    )
    selected = IntPrompt.ask(prompt=prompt, default=0 if default else None, console=CONSOLE)
    if (
        selected is None
        or selected < 0
        or selected > len(options)
        or (selected == 0 and not default)
    ):
        LOGGER.warning("Invalid Option: %s", selected)
        return create_menu(
            options=options, title=title, subtitle=subtitle, prompt=prompt, default=default
        )
    return selected
