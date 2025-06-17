import os

import pytest
from visage.mediux import Mediux
from visage.services.jellyfin import Jellyfin
from visage.services.plex import Plex


@pytest.fixture(scope="session")
def mediux_base_url() -> str:
    return os.getenv("MEDIUX__BASE_URL", default="https://api.mediux.pro")


@pytest.fixture(scope="session")
def mediux_token() -> str:
    return os.getenv("MEDIUX__TOKEN", default="IGNORED")


@pytest.fixture(scope="session")
def mediux_session(mediux_base_url: str, mediux_token: str) -> Mediux:
    return Mediux(base_url=mediux_base_url, token=mediux_token)


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
