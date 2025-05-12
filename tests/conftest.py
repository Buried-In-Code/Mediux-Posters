import os

import pytest

from mediux_posters.mediux import Mediux
from mediux_posters.services.jellyfin import Jellyfin
from mediux_posters.services.plex import Plex


@pytest.fixture(scope="session")
def mediux_base_url() -> str:
    return os.getenv("MEDIUX__BASE_URL", default="https://api.mediux.pro")


@pytest.fixture(scope="session")
def mediux_api_key() -> str:
    return os.getenv("MEDIUX__API_KEY", default="IGNORED")


@pytest.fixture(scope="session")
def mediux_session(mediux_base_url: str, mediux_api_key: str) -> Mediux:
    return Mediux(base_url=mediux_base_url, api_key=mediux_api_key)


@pytest.fixture(scope="session")
def jellyfin_base_url() -> str | None:
    return os.getenv("JELLYFIN__BASE_URL", default=None)


@pytest.fixture(scope="session")
def jellyfin_token() -> str | None:
    return os.getenv("JELLYFIN__TOKEN", default=None)


@pytest.fixture(scope="session")
def jellyfin_session(jellyfin_base_url: str | None, jellyfin_token: str | None) -> Jellyfin | None:
    if jellyfin_base_url and jellyfin_token:
        return Jellyfin(base_url=jellyfin_base_url, token=jellyfin_token)
    return None


@pytest.fixture(scope="session")
def plex_base_url() -> str | None:
    return os.getenv("PLEX__BASE_URL", default=None)


@pytest.fixture(scope="session")
def plex_token() -> str | None:
    return os.getenv("PLEX__TOKEN", default=None)


@pytest.fixture(scope="session")
def plex_session(plex_base_url: str | None, plex_token: str | None) -> Plex | None:
    if plex_base_url and plex_token:
        return Plex(base_url=plex_base_url, token=plex_token)
    return None
