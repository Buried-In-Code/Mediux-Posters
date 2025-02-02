__all__ = ["CONSOLE"]

import logging

from rich.console import Console
from rich.theme import Theme

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
