__all__ = ["Jellyfin", "Plex", "Settings"]

from pathlib import Path
from typing import Annotated, Any, ClassVar

import tomli_w as tomlwriter
from pydantic import BeforeValidator, Field
from rich.panel import Panel

from mediux_posters import get_config_root
from mediux_posters.console import CONSOLE
from mediux_posters.utils import BaseModel, blank_is_none, flatten_dict

try:
    from typing import Self  # Python >= 3.11
except ImportError:
    from typing_extensions import Self  # Python < 3.11

try:
    import tomllib as tomlreader  # Python >= 3.11
except ModuleNotFoundError:
    import tomli as tomlreader  # Python < 3.11


class Jellyfin(BaseModel):
    base_url: str = "http://127.0.0.1:8096"
    token: Annotated[str | None, BeforeValidator(blank_is_none)] = None


class Plex(BaseModel):
    base_url: str = "http://127.0.0.1:32400"
    token: Annotated[str | None, BeforeValidator(blank_is_none)] = None


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


class Settings(BaseModel):
    _file: ClassVar[Path] = get_config_root() / "settings.toml"

    exclude_usernames: list[str] = Field(default_factory=list)
    only_priority_usernames: bool = False
    priority_usernames: list[str] = Field(default_factory=list)
    jellyfin: Jellyfin = Jellyfin()
    plex: Plex = Plex()

    @classmethod
    def load(cls) -> Self:
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

    @classmethod
    def display(cls) -> None:
        default = flatten_dict(content=cls().model_dump())
        file_overrides = flatten_dict(content=cls.load().model_dump())
        default_vals = [
            f"[repr.attrib_name]{k}[/]: [repr.attrib_value]{v}[/]"
            if k in file_overrides and file_overrides[k] == v
            else f"[dim][repr.attrib_name]{k}[/]: [repr.attrib_value]{v}[/][/]"
            for k, v in default.items()
        ]
        override_vals = [
            f"[repr.attrib_name]{k}[/]: [repr.attrib_value]{v}[/]"
            for k, v in file_overrides.items()
            if k not in default or default[k] != v
        ]

        CONSOLE.print(Panel.fit("\n".join(default_vals), title="Default"))
        CONSOLE.print(Panel.fit("\n".join(override_vals), title=str(cls._file)))
