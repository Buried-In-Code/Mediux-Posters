__all__ = ["Settings", "Jellyfin", "Plex"]

from pathlib import Path
from typing import Any, ClassVar

import tomli_w as tomlwriter
from pydantic import BaseModel

from mediux_posters import get_config_root

try:
    import tomllib as tomlreader  # Python >= 3.11
except ModuleNotFoundError:
    import tomli as tomlreader  # Python < 3.11


class SettingsModel(
    BaseModel,
    populate_by_name=True,
    str_strip_whitespace=True,
    validate_assignment=True,
    extra="ignore",
):
    pass


class Jellyfin(SettingsModel):
    base_url: str = "http://127.0.0.1:8096"
    api_key: str | None = None


class Plex(SettingsModel):
    base_url: str = "http://127.0.0.1:32400"
    token: str | None = None


def _stringify_values(content: dict[str, Any]) -> dict[str, Any]:
    output = {}
    for key, value in content.items():
        if isinstance(value, bool):
            value = str(value)
        if not value:
            continue
        if isinstance(value, dict):
            value = _stringify_values(content=value)
        elif isinstance(value, list):
            value = [_stringify_values(content=x) if isinstance(x, dict) else str(x) for x in value]
        else:
            value = str(value)
        output[key] = value
    return output


class Settings(SettingsModel):
    _file: ClassVar[Path] = get_config_root() / "settings.toml"

    jellyfin: Jellyfin = Jellyfin()
    plex: Plex = Plex()

    @classmethod
    def load(cls) -> "Settings":
        if not cls._file.exists():
            cls().save()
        with cls._file.open("rb") as stream:
            content = tomlreader.load(stream)
        return cls(**content)

    def save(self) -> None:
        with self._file.open("wb") as stream:
            content = self.model_dump(by_alias=False)
            content = _stringify_values(content=content)
            tomlwriter.dump(content, stream)
