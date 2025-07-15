import json
import re
from datetime import date
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from mediux_posters.services.jellyfin import Jellyfin


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_shows(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/Library/MediaFolders",
        json=json.loads(
            Path("tests/resources/jellyfin/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Series"),
        json=json.loads(
            Path("tests/resources/jellyfin/list-shows.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = jellyfin_session.list_shows()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 33907), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_series(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/Library/MediaFolders",
        json=json.loads(
            Path("tests/resources/jellyfin/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Series"),
        json=json.loads(Path("tests/resources/jellyfin/get-show.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    result = jellyfin_session.get_show(tmdb_id=33907)
    assert result is not None

    assert result.id == "7df9cc7bbd2d497ec18b448731d3c1ec"
    assert result.imdb_id == "tt1606375"
    assert result.name == "Downton Abbey"
    assert result.premiere_date == date(2010, 9, 26)
    assert result.tmdb_id == 33907
    assert result.tv_maze_id is None
    assert result.tv_rage_id == 26615
    assert result.tvdb_id == 193131
    assert result.year == 2010


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_seasons(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url=re.compile("http://localhost/Shows/.*/Seasons.*"),
        json=json.loads(
            Path("tests/resources/jellyfin/list-seasons.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = jellyfin_session.list_seasons(show_id="7df9cc7bbd2d497ec18b448731d3c1ec")
    assert len(results) != 0

    assert results[1].id == "a32f5e92104998e8991c370feccb83e6"
    assert results[1].imdb_id is None
    assert results[1].name == "Season 1"
    assert results[1].number == 1
    assert results[1].premiere_date == date(2010, 9, 26)
    assert results[1].tmdb_id is None
    assert results[1].tv_maze_id is None
    assert results[1].tv_rage_id is None
    assert results[1].tvdb_id == 324521


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_episodes(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url=re.compile("http://localhost/Shows/.*/Episodes.*"),
        json=json.loads(
            Path("tests/resources/jellyfin/list-episodes.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = jellyfin_session.list_episodes(
        show_id="7df9cc7bbd2d497ec18b448731d3c1ec", season_id="a32f5e92104998e8991c370feccb83e6"
    )
    assert len(results) != 0

    assert results[0].id == "54cdfd0a76e33e9aa61d0946856b963f"
    assert results[0].imdb_id == "tt1608844"
    assert results[0].name == "Episode 1"
    assert results[0].number == 1
    assert results[0].premiere_date == date(2010, 9, 26)
    assert results[0].tmdb_id is None
    assert results[0].tv_maze_id is None
    assert results[0].tv_rage_id is None
    assert results[0].tvdb_id == 2887371


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_movies(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/Library/MediaFolders",
        json=json.loads(
            Path("tests/resources/jellyfin/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Movie"),
        json=json.loads(
            Path("tests/resources/jellyfin/list-movies.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = jellyfin_session.list_movies()
    assert len(results) != 0
    result = next(iter(x for x in results if x.tmdb_id == 16859), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_movie(jellyfin_session: Jellyfin | None, httpx_mock: HTTPXMock) -> None:
    if jellyfin_session is None:
        jellyfin_session = Jellyfin(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/Library/MediaFolders",
        json=json.loads(
            Path("tests/resources/jellyfin/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Movie"),
        json=json.loads(
            Path("tests/resources/jellyfin/get-movie.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    result = jellyfin_session.get_movie(tmdb_id=16859)
    assert result is not None

    assert result.id == "3fc8b00200041d83e3118646d82ba4e4"
    assert result.imdb_id == "tt0097814"
    assert result.name == "Kiki's Delivery Service"
    assert result.premiere_date == date(1989, 7, 29)
    assert result.tmdb_collection_id is None
    assert result.tmdb_id == 16859
    assert result.year == 1989
