import json
import re
from datetime import date
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from mediux_posters.services.plex.api_service import Plex


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_shows(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-shows.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-seasons.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-episodes.json").read_text()),
        is_reusable=True,
    )

    results = plex_session.list_shows()
    assert results is not None
    result = next(iter(x for x in results if x.tmdb_id == 33907), None)
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
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-show.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-seasons.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-episodes.json").read_text()),
        is_reusable=True,
    )

    result = plex_session.get_show(tmdb_id=33907)
    assert result is not None

    assert result.id == 108617
    assert result.imdb_id == "tt1606375"
    assert result.name == "Downton Abbey"
    assert result.premiere_date == date(2010, 9, 26)
    assert result.tmdb_id == 33907
    assert result.tvdb_id == 193131
    assert result.year == 2010
    assert len(result.seasons) != 0
    assert result.seasons[1].id == 108654
    assert result.seasons[1].imdb_id is None
    assert result.seasons[1].name == "Series 1"
    assert result.seasons[1].number == 1
    assert result.seasons[1].premiere_date is None
    assert result.seasons[1].tmdb_id == 44728
    assert result.seasons[1].tvdb_id == 324521
    assert len(result.seasons[1].episodes) != 0
    assert result.seasons[1].episodes[0].id == 108655
    assert result.seasons[1].episodes[0].imdb_id == "tt1608844"
    assert result.seasons[1].episodes[0].name == "Episode #1.1"
    assert result.seasons[1].episodes[0].number == 1
    assert result.seasons[1].episodes[0].premiere_date == date(2010, 9, 26)
    assert result.seasons[1].episodes[0].tmdb_id == 779837
    assert result.seasons[1].episodes[0].tvdb_id == 2887371


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_movies(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-movies.json").read_text()),
        is_reusable=True,
    )

    results = plex_session.list_movies()
    assert len(results) != 0
    result = next(iter(x for x in results if x.tmdb_id == 16859), None)
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
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-movie.json").read_text()),
        is_reusable=True,
    )

    result = plex_session.get_movie(tmdb_id=16859)
    assert result is not None

    assert result.id == 110049
    assert result.imdb_id == "tt0097814"
    assert result.name == "Kiki's Delivery Service"
    assert result.premiere_date == date(1989, 7, 29)
    assert result.tmdb_id == 16859
    assert result.tvdb_id is None
    assert result.year == 1989


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_collections(plex_session: Plex | None, httpx_mock: HTTPXMock) -> None:
    if plex_session is None:
        plex_session = Plex(base_url="http://localhost", token="INVALID")  # noqa: S106
    httpx_mock.add_response(
        url="http://localhost/library/sections",
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-collections.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-collection.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-collection-movies.json").read_text()),
        is_reusable=True,
    )

    results = plex_session.list_collections()
    assert len(results) != 0
    result = next(iter(x for x in results if x.tmdb_id == 529), None)
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
        json=json.loads(Path("tests/resources/plex/list-libraries.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-collections.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/get-collection.json").read_text()),
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json=json.loads(Path("tests/resources/plex/list-collection-movies.json").read_text()),
        is_reusable=True,
    )

    result = plex_session.get_collection(tmdb_id=529)
    assert result is not None

    assert result.id == 110049
    assert result.name == "Wallace & Gromit Collection"
    assert result.tmdb_id == 529
    assert len(result.movies) != 0
    assert result.movies[0].id == 110049
    assert result.movies[0].imdb_id == "tt0097814"
    assert result.movies[0].name == "A Grand Day Out"
    assert result.movies[0].premiere_date == date(1989, 7, 29)
    assert result.movies[0].tmdb_id == 16859
    assert result.movies[0].tvdb_id is None
    assert result.movies[0].year == 1989
