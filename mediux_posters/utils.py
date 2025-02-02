__all__ = ["BaseModel", "MediaType", "blank_is_none", "delete_folder", "flatten_dict", "slugify"]

import logging
import re
import unicodedata
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel as PydanticModel
from rich.panel import Panel

from mediux_posters.console import CONSOLE

LOGGER = logging.getLogger(__name__)


class BaseModel(
    PydanticModel,
    populate_by_name=True,
    str_strip_whitespace=True,
    validate_assignment=True,
    extra="ignore",
):
    def display(self) -> None:
        content = flatten_dict(content=self.model_dump())
        content_vals = [
            f"[repr.attrib_name]{k}[/]: [repr.attrib_value]{v}[/]" for k, v in content.items()
        ]
        CONSOLE.print(Panel.fit("\n".join(content_vals), title=type(self).__name__))


class MediaType(str, Enum):
    SHOW = "show"
    SEASON = "season"
    EPISODE = "episode"
    MOVIE = "movie"
    COLLECTION = "collection"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def delete_folder(folder: Path) -> None:
    if folder.is_dir():
        for entry in folder.iterdir():
            if entry.is_dir():
                delete_folder(folder=entry)
            else:
                entry.unlink(missing_ok=True)
        folder.rmdir()
    else:
        folder.unlink(missing_ok=True)


def flatten_dict(content: dict[str, Any], parent_key: str = "") -> dict[str, Any]:
    items = {}
    for key, value in content.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_dict(content=value, parent_key=new_key))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            for index, entry in enumerate(value):
                items.update(flatten_dict(content=entry, parent_key=f"{new_key}[{index}]"))
        else:
            items[new_key] = value
    return dict(sorted(items.items()))


def blank_is_none(value: str) -> str | None:
    """Enforces blank strings to be None."""
    return value if value else None
