import hashlib
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from mediux_posters.mediux import Mediux
from mediux_posters.mediux.schemas import FileType
from mediux_posters.utils import MediaType


def test_list_show_sets(mediux_session: Mediux) -> None:
    results = mediux_session.list_show_sets(tmdb_id=33907)
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 28831), None)
    assert result is not None

    assert len(result.files) != 0
    assert result.files[0].id == "05f1a0a7-18f6-495c-8193-42400d74e4cc"
    assert result.files[0].file_type == FileType.TITLE_CARD
    assert result.files[0].show_id is None
    assert result.files[0].season_id is None
    assert result.files[0].episode_id == 1106251
    assert result.files[0].movie_id is None
    assert result.files[0].collection_id is None
    assert result.id == 28831
    assert result.set_title == "Downton Abbey (2010) Set"
    assert result.show.release_date == date(2010, 9, 26)
    assert len(result.show.seasons) != 0
    assert len(result.show.seasons[0].episodes) != 0
    assert result.show.seasons[0].episodes[0].id == 779832
    assert result.show.seasons[0].episodes[0].number == 2
    assert result.show.seasons[0].episodes[0].title == "Christmas at Downton Abbey"
    assert result.show.seasons[0].id == 44727
    assert result.show.seasons[0].title == "Specials"
    assert result.show.seasons[0].number == 0
    assert result.show.title == "Downton Abbey"
    assert result.show.tmdb_id == 33907
    assert result.username == "JackTaylor803"


def test_list_show_sets_filtered(mediux_session: Mediux) -> None:
    results = mediux_session.list_show_sets(tmdb_id=33907, exclude_usernames=["JackTaylor803"])
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 28831), None)
    assert result is None


def test_list_show_sets_invalid(mediux_session: Mediux) -> None:
    results = mediux_session.list_show_sets(tmdb_id=-1)
    assert len(results) == 0


def test_get_show_set(mediux_session: Mediux) -> None:
    result = mediux_session.get_show_set(set_id=28831)
    assert result is not None


def test_get_show_set_invalid(mediux_session: Mediux) -> None:
    result = mediux_session.get_show_set(set_id=-1)
    assert result is None


def test_list_collection_sets(mediux_session: Mediux) -> None:
    results = mediux_session.list_collection_sets(tmdb_id=573436)
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 24404), None)
    assert result is not None

    assert len(result.collection.movies) != 0
    assert result.collection.movies[0].release_date == date(2018, 12, 6)
    assert result.collection.movies[0].title == "Spider-Man: Into the Spider-Verse"
    assert result.collection.movies[0].tmdb_id == 324857
    assert result.collection.title == "Spider-Man: Spider-Verse Collection"
    assert result.collection.tmdb_id == 573436
    assert len(result.files) != 0
    assert result.files[0].id == "3ae60cf9-ad99-449c-971f-5d7c6eaba02f"
    assert result.files[0].file_type == FileType.POSTER
    assert result.files[0].show_id is None
    assert result.files[0].season_id is None
    assert result.files[0].episode_id is None
    assert result.files[0].movie_id == 324857
    assert result.files[0].collection_id is None
    assert result.id == 24404
    assert result.set_title == "Spider-Man: Spider-Verse Collection"
    assert result.username == "willtong93"


def test_list_collection_sets_filtered(mediux_session: Mediux) -> None:
    results = mediux_session.list_collection_sets(tmdb_id=573436, exclude_usernames=["willtong93"])
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 24404), None)
    assert result is None


def test_list_collection_sets_invalid(mediux_session: Mediux) -> None:
    results = mediux_session.list_collection_sets(tmdb_id=-1)
    assert len(results) == 0


def test_get_collection_set(mediux_session: Mediux) -> None:
    result = mediux_session.get_collection_set(set_id=24404)
    assert result is not None


def test_get_collection_set_invalid(mediux_session: Mediux) -> None:
    result = mediux_session.get_collection_set(set_id=-1)
    assert result is None


def test_list_movie_sets(mediux_session: Mediux) -> None:
    results = mediux_session.list_movie_sets(tmdb_id=535544)
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 11023), None)
    assert result is not None

    assert len(result.files) != 0
    assert result.files[0].id == "b9dd4856-b95f-42b4-8e9a-633f7d152fa4"
    assert result.files[0].file_type == FileType.POSTER
    assert result.files[0].show_id is None
    assert result.files[0].season_id is None
    assert result.files[0].episode_id is None
    assert result.files[0].movie_id == 535544
    assert result.files[0].collection_id is None
    assert result.id == 11023
    assert result.movie.release_date == date(2019, 9, 12)
    assert result.movie.title == "Downton Abbey"
    assert result.movie.tmdb_id == 535544
    assert result.set_title == "Downton Abbey (2019) Set"
    assert result.username == "fwlolx"


def test_list_movie_sets_filtered(mediux_session: Mediux) -> None:
    results = mediux_session.list_movie_sets(tmdb_id=535544, exclude_usernames=["fwlolx"])
    assert len(results) != 0
    result = next(iter(x for x in results if x.id == 11023), None)
    assert result is None


def test_list_movie_sets_invalid(mediux_session: Mediux) -> None:
    results = mediux_session.list_movie_sets(tmdb_id=-1)
    assert len(results) == 0


def test_get_movie_set(mediux_session: Mediux) -> None:
    result = mediux_session.get_movie_set(set_id=11023)
    assert result is not None


def test_get_movie_set_invalid(mediux_session: Mediux) -> None:
    result = mediux_session.get_movie_set(set_id=-1)
    assert result is None


def compute_file_hash(file: Path) -> str:
    hasher = hashlib.sha256()
    with file.open("rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def test_download_image(mediux_session: Mediux) -> None:
    expected_image = Path("tests/resources/img-poster.jpg")

    with NamedTemporaryFile() as output:
        output_file = Path(output.name)
        mediux_session.download_image(
            file_id="b9dd4856-b95f-42b4-8e9a-633f7d152fa4", output=output_file
        )

        assert compute_file_hash(expected_image) == compute_file_hash(output_file), (
            "Downloaded image does not match expected image"
        )


def test_season_name_none(mediux_session: Mediux) -> None:
    results = mediux_session.list_sets(media_type=MediaType.SHOW, tmdb_id=95479)
    assert len(results) != 0
    assert results[0].show.seasons[2].title is None
