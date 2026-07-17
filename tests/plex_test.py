import re

from requests_mock import Mocker

from mediux_posters.services import Plex


def add_list_libraries_mock(mocker: Mocker) -> None:
    mocker.get(
        url="http://localhost/library/sections",
        json={
            "MediaContainer": {
                "Directory": [
                    {"key": 1, "title": "Movies", "type": "movie"},
                    {"key": 2, "title": "TV shows", "type": "show"},
                ]
            }
        },
    )


def add_list_shows_mock(mocker: Mocker) -> None:
    mocker.get(
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
    )


def add_get_show_mock(mocker: Mocker) -> None:
    mocker.get(
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
    )


def add_list_seasons_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={"MediaContainer": {"Metadata": [{"ratingKey": "119056", "index": 1}]}},
    )


def add_list_episodes_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={"MediaContainer": {"Metadata": [{"ratingKey": "119057", "index": 1}]}},
    )


def add_list_collections_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/sections/.*/collections\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {"ratingKey": "1897", "title": "Spider-Man: Spider-Verse Collection"},
                    {"ratingKey": "120689", "title": "Spider-Man Collection"},
                ]
            }
        },
    )


def add_get_collection_mock(mocker: Mocker) -> None:
    mocker.get(
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
    )


def add_list_collection_movies_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/metadata/.*/children\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "141762",
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
    )


def add_list_movies_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/sections/.*/all\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "141762",
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
    )


def add_get_movie_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile(r"http://localhost/library/sections/.*\?includeGuids=1"),
        json={
            "MediaContainer": {
                "Metadata": [
                    {
                        "ratingKey": "141762",
                        "title": "Spider-Man: Into the Spider-Verse",
                        "year": 2018,
                        "Guid": [{"id": "tmdb://324857"}],
                    }
                ]
            }
        },
    )


def test_list_shows(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_shows_mock(mocker=requests_mock)

    results = plex_session.list_shows()
    assert results is not None

    result = next(iter(x for x in results if x.tmdb_id == 1457), None)
    assert result is not None


def test_get_show(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_get_show_mock(mocker=requests_mock)

    result = plex_session.get_show(tmdb_id=1457)
    assert result is not None

    assert result.id == 119055
    assert result.name == "Pride and Prejudice"
    assert result.tmdb_id == 1457
    assert result.year == 1995


def test_list_seasons(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_seasons_mock(mocker=requests_mock)

    results = plex_session.list_seasons(show_id=119055)
    assert len(results) != 0

    assert results[0].id == 119056


def test_list_episodes(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_episodes_mock(mocker=requests_mock)

    results = plex_session.list_episodes(show_id=119055, season_id=119056)
    assert len(results) != 0

    assert results[0].id == 119057


def test_list_collections(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_collections_mock(mocker=requests_mock)
        add_get_collection_mock(mocker=requests_mock)

    results = plex_session.list_collections()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 573436), None)
    assert result is not None


def test_get_collection(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_collections_mock(mocker=requests_mock)
        add_get_collection_mock(mocker=requests_mock)

    result = plex_session.get_collection(tmdb_id=573436)
    assert result is not None

    assert result.id == 1897
    assert result.name == "Spider-Man: Spider-Verse Collection"
    assert result.tmdb_id == 573436


def test_list_collection_movies(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_collection_movies_mock(mocker=requests_mock)

    results = plex_session.list_collection_movies(collection_id=1897)
    assert len(results) != 0

    assert results[0].id == 141762
    assert results[0].name == "Spider-Man: Into the Spider-Verse"
    assert results[0].tmdb_id == 324857
    assert results[0].year == 2018


def test_list_movies(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_movies_mock(mocker=requests_mock)

    results = plex_session.list_movies()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 324857), None)
    assert result is not None


def test_get_movie(plex_session: Plex, requests_mock: Mocker) -> None:
    if "localhost" in plex_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_get_movie_mock(mocker=requests_mock)

    result = plex_session.get_movie(tmdb_id=324857)
    assert result is not None

    assert result.id == 141762
    assert result.name == "Spider-Man: Into the Spider-Verse"
    assert result.tmdb_id == 324857
    assert result.year == 2018
