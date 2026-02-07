__all__ = ["CONSOLE"]

from rich.console import Console
from rich.theme import Theme

CONSOLE = Console(
    theme=Theme(
        {
            "title": "#4682B4",
            "logging.level.debug": "dim white",
            "logging.level.info": "white",
            "logging.level.warning": "yellow",
            "logging.level.error": "bold red",
            "logging.level.critical": "bold magenta",
        }
    )
)
