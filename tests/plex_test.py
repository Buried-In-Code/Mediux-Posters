import re

import pytest
from pytest_httpx import HTTPXMock

from mediux_posters.services import Plex


def add_list_libraries_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url="http://localhost/library/sections",
        json={
            "MediaContainer": {
                "Directory": [
                    {"key": 1, "title": "Movies", "type": "movie"},
                    {"key": 2, "title": "TV shows", "type": "show"},
                ]
            }
        },
        is_reusable=True,
    )


def add_list_shows_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "119055",
                        "title": "Pride and Prejudice",
                        "year": 1995,
                        "Guid": [{"id": "tmdb://1457"}],
                    },
                    {
                        "ratingKey": "109248",
                        "title": "The Adventures of Tintin",
                        "year": 1991,
                        "Guid": [{"id": "tmdb://1570"}],
                    },
                ]
            }
        },
        is_reusable=True,
    )


def add_get_show_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "119055",
                        "title": "Pride and Prejudice",
                        "year": 1995,
                        "Guid": [{"id": "tmdb://1457"}],
                    }
                ]
            }
        },
        is_reusable=True,
    )


def add_list_seasons_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={"MediaContainer": {"Metadata": [{"ratingKey": "119056"}]}},
        is_reusable=True,
    )


def add_list_episodes_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={"MediaContainer": {"Metadata": [{"ratingKey": "119057"}]}},
        is_reusable=True,
    )


def add_list_collections_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {"ratingKey": "1897", "title": "Spider-Man: Spider-Verse Collection"},
                    {"ratingKey": "120689", "title": "Spider-Man Collection"},
                ]
            }
        },
        is_reusable=True,
    )


def add_get_collection_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "1897",
                        "title": "Spider-Man: Spider-Verse Collection",
                        "Label": [{"tag": "Tmdb-573436"}],
                    }
                ]
            }
        },
        is_reusable=True,
    )


def add_list_collection_movies_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "110309",
                        "title": "Spider-Man: Into the Spider-Verse",
                        "year": 2018,
                        "Guid": [{"id": "tmdb://324857"}],
                    },
                    {
                        "ratingKey": "110118",
                        "title": "Spider-Man: Across the Spider-Verse",
                        "year": 2023,
                        "Guid": [{"id": "tmdb://569094"}],
                    },
                ]
            }
        },
        is_reusable=True,
    )


def add_list_movies_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "110309",
                        "title": "Spider-Man: Into the Spider-Verse",
                        "year": 2018,
                        "Guid": [{"id": "tmdb://324857"}],
                    },
                    {
                        "ratingKey": "110118",
                        "title": "Spider-Man: Across the Spider-Verse",
                        "year": 2023,
                        "Guid": [{"id": "tmdb://569094"}],
                    },
                ]
            }
        },
        is_reusable=True,
    )


def add_get_movie_mock(mock: HTTPXMock) -> None:
    mock.add_response(
        url=re.compile(r"http://localhost/library/sections/.*\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "110309",
                        "title": "Spider-Man: Into the Spider-Verse",
                        "year": 2018,
                        "Guid": [{"id": "tmdb://324857"}],
                    }
                ]
            }
        },
        is_reusable=True,
    )


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_shows(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_list_shows_mock(mock=httpx_mock)

    results = plex_session.list_shows()
    assert results is not None

    result = next(iter(x for x in results if x.tmdb_id == 1457), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_show(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_get_show_mock(mock=httpx_mock)

    result = plex_session.get_show(tmdb_id=1457)
    assert result is not None

    assert result.id == 119055
    assert result.name == "Pride and Prejudice"
    assert result.tmdb_id == 1457
    assert result.year == 1995


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_seasons(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_seasons_mock(mock=httpx_mock)

    results = plex_session.list_seasons(show_id=119055)
    assert len(results) != 0

    assert results[0].id == 119056


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_episodes(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_episodes_mock(mock=httpx_mock)

    results = plex_session.list_episodes(show_id=119055, season_id=119056)
    assert len(results) != 0

    assert results[0].id == 119057


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_collections(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_list_collections_mock(mock=httpx_mock)
    add_get_collection_mock(mock=httpx_mock)

    results = plex_session.list_collections()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 573436), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_collection(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_list_collections_mock(mock=httpx_mock)
    add_get_collection_mock(mock=httpx_mock)

    result = plex_session.get_collection(tmdb_id=573436)
    assert result is not None

    assert result.id == 1897
    assert result.name == "Spider-Man: Spider-Verse Collection"
    assert result.tmdb_id == 573436


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_collection_movies(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_collection_movies_mock(mock=httpx_mock)

    results = plex_session.list_collection_movies(collection_id=1897)
    assert len(results) != 0

    assert results[0].id == 110309
    assert results[0].name == "Spider-Man: Into the Spider-Verse"
    assert results[0].tmdb_id == 324857
    assert results[0].year == 2018


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_list_movies(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_list_movies_mock(mock=httpx_mock)

    results = plex_session.list_movies()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 324857), None)
    assert result is not None


@pytest.mark.httpx_mock(
    should_mock=lambda request: request.url.host == "localhost",
    assert_all_responses_were_requested=False,
)
def test_get_movie(plex_session: Plex, httpx_mock: HTTPXMock) -> None:
    add_list_libraries_mock(mock=httpx_mock)
    add_get_movie_mock(mock=httpx_mock)

    result = plex_session.get_movie(tmdb_id=324857)
    assert result is not None

    assert result.id == 110309
    assert result.name == "Spider-Man: Into the Spider-Verse"
    assert result.tmdb_id == 324857
    assert result.year == 2018
