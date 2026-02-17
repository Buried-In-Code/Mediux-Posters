import os
from datetime import date, datetime

import pytest

from mediux_posters.mediux import File, FileType, Mediux, MovieSet as SetData
from mediux_posters.mediux.schemas import Movie as MediuxMedia
from mediux_posters.services import Jellyfin, Movie as Media, Plex
from mediux_posters.services.service_cache import ServiceCache


@pytest.fixture(scope="session")
def cache() -> ServiceCache:
    return ServiceCache()


@pytest.fixture(scope="session")
def mediux_base_url() -> str:
    return os.getenv("MEDIUX__BASE_URL", default="https://images.mediux.io")


@pytest.fixture(scope="session")
def mediux_token() -> str:
    return os.getenv("MEDIUX__TOKEN", default="UNSET")


@pytest.fixture(scope="session")
def mediux_session(mediux_base_url: str, mediux_token: str) -> Mediux:
    mediux = Mediux(base_url=mediux_base_url, token=mediux_token)
    assert mediux.validate() is True
    return mediux


@pytest.fixture(scope="session")
def jellyfin_base_url() -> str:
    return os.getenv("JELLYFIN__BASE_URL", default="http://localhost")


@pytest.fixture(scope="session")
def jellyfin_token() -> str:
    return os.getenv("JELLYFIN__TOKEN", default="UNSET")


@pytest.fixture(scope="session")
def jellyfin_session(jellyfin_base_url: str, jellyfin_token: str, cache: ServiceCache) -> Jellyfin:
    session = Jellyfin(base_url=jellyfin_base_url, token=jellyfin_token, cache=cache)
    if jellyfin_base_url != "http://localhost":
        assert session.validate() is True
    return session


@pytest.fixture(scope="session")
def plex_base_url() -> str:
    return os.getenv("PLEX__BASE_URL", default="http://localhost")


@pytest.fixture(scope="session")
def plex_token() -> str:
    return os.getenv("PLEX__TOKEN", default="UNSET")


@pytest.fixture(scope="session")
def plex_session(plex_base_url: str, plex_token: str, cache: ServiceCache) -> Plex:
    session = Plex(base_url=plex_base_url, token=plex_token, cache=cache)
    if plex_base_url != "http://localhost":
        assert session.validate() is True
    return session


@pytest.fixture
def media_obj() -> Media:
    return Media(id=1, name="Test Movie", tmdb_id=1, year=2025)


@pytest.fixture
def set_data() -> SetData:
    return SetData(
        date_updated=datetime.now(),  # noqa: DTZ005
        files=[
            File(
                id="file-poster-id",
                file_type=FileType.POSTER,
                modified_on=datetime.now(),  # noqa: DTZ005
                movie_id=1,
            )
        ],
        id=1,
        movie_id=MediuxMedia(id=1, release_date=date.today(), title="Test Movie"),  # noqa: DTZ011
        set_title="Test Set",
        username="Test User",
    )
