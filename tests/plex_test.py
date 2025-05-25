import json
import re
from datetime import date
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from mediux_posters.services.plex import Plex


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_shows(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-shows.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    results = plex_session.list_shows()
    assert results is not None

    result = next(iter(x for x in results if x.tmdb_id == 131378), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_show(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-show.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    result = plex_session.get_show(tmdb_id=131378)
    assert result is not None

    assert result.id == 109436
    assert result.imdb_id == "tt15248880"
    assert result.name == "Adventure Time: Fionna & Cake"
    assert result.premiere_date == date(2023, 8, 31)
    assert result.tmdb_id == 131378
    assert result.tvdb_id == 408850
    assert result.year == 2023


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_seasons(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-seasons.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    results = plex_session.list_seasons(show_id=109436)
    assert len(results) != 0

    assert results[0].id == 109437
    assert results[0].imdb_id is None
    assert results[0].name == "Season 1"
    assert results[0].number == 1
    assert results[0].premiere_date is None
    assert results[0].tmdb_id == 206322
    assert results[0].tvdb_id == 1950683


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_episodes(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/list-episodes.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = plex_session.list_episodes(show_id=109436, season_id=109437)
    assert len(results) != 0

    assert results[0].id == 109438
    assert results[0].imdb_id == "tt15251002"
    assert results[0].name == "Fionna Campbell"
    assert results[0].number == 1
    assert results[0].premiere_date == date(2023, 8, 31)
    assert results[0].tmdb_id == 4582728
    assert results[0].tvdb_id == 8619274


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_collections(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/list-collections.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/get-collection.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = plex_session.list_collections()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 125574), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_collection(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/list-collections.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/get-collection.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    result = plex_session.get_collection(tmdb_id=125574)
    assert result is not None

    assert result.id == 120713
    assert result.name == "The Amazing Spider-Man Collection"
    assert result.tmdb_id == 125574


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_collection_movies(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(
            Path("tests/resources/plex/list-collection-movies.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )

    results = plex_session.list_collection_movies(collection_id=120713)
    assert len(results) != 0

    assert results[0].id == 120717
    assert results[0].imdb_id == "tt0948470"
    assert results[0].name == "The Amazing Spider-Man"
    assert results[0].premiere_date == date(2012, 6, 28)
    assert results[0].tmdb_id == 1930
    assert results[0].tvdb_id == 473
    assert results[0].year == 2012


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_movies(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-movies.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    results = plex_session.list_movies()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 431580), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_movie(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(
            Path("tests/resources/plex/list-libraries.json").read_text(encoding="UTF-8")
        ),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-movie.json").read_text(encoding="UTF-8")),
        is_reusable=True,
    )

    result = plex_session.get_movie(tmdb_id=431580)
    assert result is not None

    assert result.id == 102210
    assert result.imdb_id == "tt6324278"
    assert result.name == "Abominable"
    assert result.premiere_date == date(2019, 9, 19)
    assert result.tmdb_id == 431580
    assert result.tvdb_id == 12176
    assert result.year == 2019
