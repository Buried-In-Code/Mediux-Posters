import re

from requests_mock import Mocker

from mediux_posters.services import Jellyfin


def add_list_libraries_mock(mocker: Mocker) -> None:
    mocker.get(
        url="http://localhost/Library/MediaFolders",
        json={
            "Items": [
                {
                    "Id": "f137a2dd21bbc1b99aa5c0f6bf02a805",
                    "Name": "Movies",
                    "CollectionType": "movies",
                },
                {
                    "Id": "a656b907eb3a73532e40e44b968d0225",
                    "Name": "Shows",
                    "CollectionType": "tvshows",
                },
            ]
        },
    )


def add_list_shows_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Series"),
        json={
            "Items": [
                {
                    "Id": "ac666209a446f29d7538a5fe156ab440",
                    "Name": "Pride and Prejudice",
                    "ProductionYear": 1995,
                    "ProviderIds": {"Tmdb": "1457"},
                },
                {
                    "Id": "8d3a9d3ed27db0df33c049c82a9f695e",
                    "Name": "The Adventures of Tintin",
                    "ProductionYear": 1991,
                    "ProviderIds": {"Tmdb": "1570"},
                },
            ]
        },
    )


def add_get_show_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Series"),
        json={
            "Items": [
                {
                    "Id": "ac666209a446f29d7538a5fe156ab440",
                    "Name": "Pride and Prejudice",
                    "ProductionYear": 1995,
                    "ProviderIds": {"Tmdb": "1457"},
                }
            ]
        },
    )


def add_list_seasons_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Shows/.*/Seasons.*"),
        json={"Items": [{"Id": "7b63c71486e0580c8154b23ef829cf99", "IndexNumber": 1}]},
    )


def add_list_episodes_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Shows/.*/Episodes.*"),
        json={"Items": [{"Id": "a375ae1a31b78c063f5e20c81d1f21e4", "IndexNumber": 1}]},
    )


def add_list_movies_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Movie"),
        json={
            "Items": [
                {
                    "Id": "208bacccc47c1a3e6cafa819c16b9c36",
                    "Name": "Spider-Man: Into the Spider-Verse",
                    "ProductionYear": 2018,
                    "ProviderIds": {"Tmdb": "324857"},
                },
                {
                    "Id": "71c078c7fcc638ae4a6a5afda76edad8",
                    "Name": "Spider-Man: Across the Spider-Verse",
                    "ProductionYear": 2023,
                    "ProviderIds": {"Tmdb": "569094"},
                },
            ]
        },
    )


def add_get_movie_mock(mocker: Mocker) -> None:
    mocker.get(
        url=re.compile("http://localhost/Items.*IncludeItemTypes=Movie"),
        json={
            "Items": [
                {
                    "Id": "208bacccc47c1a3e6cafa819c16b9c36",
                    "Name": "Spider-Man: Into the Spider-Verse",
                    "ProductionYear": 2018,
                    "ProviderIds": {"Tmdb": "324857"},
                }
            ]
        },
    )


def test_list_shows(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_shows_mock(mocker=requests_mock)

    results = jellyfin_session.list_shows()
    assert len(results) != 0

    result = next(iter(x for x in results if x.tmdb_id == 1457), None)
    assert result is not None


def test_get_series(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_get_show_mock(mocker=requests_mock)

    result = jellyfin_session.get_show(tmdb_id=1457)
    assert result is not None

    assert result.id == "ac666209a446f29d7538a5fe156ab440"
    assert result.name == "Pride and Prejudice"
    assert result.tmdb_id == 1457
    assert result.year == 1995


def test_list_seasons(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_seasons_mock(mocker=requests_mock)

    results = jellyfin_session.list_seasons(show_id="ac666209a446f29d7538a5fe156ab440")
    assert len(results) != 0

    assert results[0].id == "7b63c71486e0580c8154b23ef829cf99"


def test_list_episodes(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_episodes_mock(mocker=requests_mock)

    results = jellyfin_session.list_episodes(
        show_id="ac666209a446f29d7538a5fe156ab440", season_id="7b63c71486e0580c8154b23ef829cf99"
    )
    assert len(results) != 0

    assert results[0].id == "a375ae1a31b78c063f5e20c81d1f21e4"


def test_list_movies(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_list_movies_mock(mocker=requests_mock)

    results = jellyfin_session.list_movies()
    assert len(results) != 0
    result = next(iter(x for x in results if x.tmdb_id == 569094), None)
    assert result is not None


def test_get_movie(jellyfin_session: Jellyfin, requests_mock: Mocker) -> None:
    if "localhost" in jellyfin_session.base_url:
        add_list_libraries_mock(mocker=requests_mock)
        add_get_movie_mock(mocker=requests_mock)

    result = jellyfin_session.get_movie(tmdb_id=324857)
    assert result is not None

    assert result.id == "208bacccc47c1a3e6cafa819c16b9c36"
    assert result.name == "Spider-Man: Into the Spider-Verse"
    assert result.tmdb_id == 324857
    assert result.year == 2018
