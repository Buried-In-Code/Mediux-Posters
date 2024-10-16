__all__ = ["find_poster", "slugify"]

import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal

from mediux_posters import get_cache_root

LOGGER = logging.getLogger(__name__)


def find_poster(
    mediatype: Literal["shows", "movies", "collections"], folder: str, filename: str
) -> Path:
    cover_folder = get_cache_root() / "covers" / mediatype / slugify(folder)
    return cover_folder / f"{slugify(filename)}.jpg"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")
