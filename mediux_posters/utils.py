__all__ = ["find_poster", "slugify"]

import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal

from mediux_posters import get_project_root

LOGGER = logging.getLogger(__name__)


def find_poster(
    mediatype: Literal["shows", "movies", "collections"], folder: str, filename: str
) -> Path | None:
    cover_folder = get_project_root() / "covers" / mediatype / slugify(folder)
    poster_path = cover_folder / f"{slugify(filename)}.jpg"
    if poster_path.exists():
        return poster_path
    return None


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")
