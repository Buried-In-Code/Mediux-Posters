import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup
from pydantic import Field
from requests import get
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout
from rich.progress import Progress

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.utils import BaseModel

LOGGER = logging.getLogger(__name__)


class Episode(BaseModel):
    number: int
    name: str
    title_card_id: str | None = None


class Season(BaseModel):
    number: int
    name: str
    poster_id: str | None = None
    episodes: list[Episode]


class Show(BaseModel):
    tmdb_id: int
    name: str
    year: int | None = None
    poster_id: str | None = None
    backdrop_id: str | None = None
    seasons: list[Season]

    @property
    def filename(self) -> str:
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name


class Movie(BaseModel):
    tmdb_id: int
    name: str
    year: int | None = None
    poster_id: str | None = None

    @property
    def filename(self) -> str:
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name


class Collection(BaseModel):
    name: str
    poster_id: str | None = None
    backdrop_id: str | None = None
    movies: list[Movie] = Field(default_factory=list)


class MediuxSet(BaseModel):
    id: int
    name: str
    show: Show | None = None
    movie: Movie | None = None
    collection: Collection | None = None


def parse_to_dict(input_string: str) -> dict:
    clean_string = input_string.replace('\\\\\\"', "").replace("\\", "").replace("u0026", "&")
    json_data = clean_string[clean_string.find("{") : clean_string.rfind("}") + 1]
    return json.loads(json_data)


class Mediux:
    web_url: str = "https://mediux.pro"
    api_url: str = "https://api.mediux.pro"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "Windows",
        }

    def _list_sets(self, url: str) -> list[dict]:
        try:
            response = get(url, timeout=30)
            if response.status_code not in (200, 500):
                LOGGER.error(response.text)
                return []
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s'", url)
            return []
        except HTTPError as err:
            LOGGER.error(err.response.text)
            return []
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.find_all("script"):
            if "files" in script.text and "set" in script.text and "Set Link\\" not in script.text:
                return parse_to_dict(script.text).get("sets", [])
        return []

    def list_show_sets(self, tmdb_id: int) -> list[dict]:
        show_url = f"{self.web_url}/shows/{tmdb_id}"
        LOGGER.info("Downloading show information from '%s'", show_url)

        return self._list_sets(url=show_url)

    def list_movie_sets(self, tmdb_id: int) -> list[dict]:
        movie_url = f"{self.web_url}/movies/{tmdb_id}"
        LOGGER.info("Downloading movie information from '%s'", movie_url)

        return self._list_sets(url=movie_url)

    def list_collection_sets(self, tmdb_id: int) -> list[dict]:
        collection_url = f"{self.web_url}/collections/{tmdb_id}"
        LOGGER.info("Downloading collection information from '%s'", collection_url)

        return self._list_sets(url=collection_url)

    def scrape_set(self, set_id: int) -> dict:
        set_url = f"{self.web_url}/sets/{set_id}"
        LOGGER.info("Downloading set information from '%s'", set_url)

        try:
            response = get(set_url, timeout=30)
            if response.status_code not in (200, 500):
                LOGGER.error(response.text)
                return {}
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s'", set_url)
            return {}
        except HTTPError as err:
            LOGGER.error(err.response.text)
            return {}
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.find_all("script"):
            if "files" in script.text and "set" in script.text and "Set Link\\" not in script.text:
                return parse_to_dict(script.text).get("set", {})
        return {}

    def _get_file_id(self, data: dict, file_type: str, id_key: str, id_value: str) -> str | None:
        return next(
            (
                x["id"]
                for x in data["files"]
                if x["fileType"] == file_type
                and id_key in x
                and x[id_key]
                and x[id_key]["id"] == id_value
            ),
            None,
        )

    def process_data(self, data: dict, include_movies: bool = False) -> MediuxSet:
        show, movie, collection = None, None, None

        if data.get("show"):
            show = Show(
                tmdb_id=data["show"]["id"],
                name=data["show"]["name"],
                year=int(data["show"]["first_air_date"][:4]),
                poster_id=self._get_file_id(
                    data=data, file_type="poster", id_key="show_id", id_value=data["show"]["id"]
                ),
                backdrop_id=self._get_file_id(
                    data=data,
                    file_type="backdrop",
                    id_key="show_id_backdrop",
                    id_value=data["show"]["id"],
                ),
                seasons=[
                    Season(
                        number=int(season["season_number"]),
                        name=season["name"],
                        poster_id=self._get_file_id(
                            data=data, file_type="poster", id_key="season_id", id_value=season["id"]
                        ),
                        episodes=[
                            Episode(
                                number=int(episode["episode_number"]),
                                name=episode["episode_name"],
                                title_card_id=self._get_file_id(
                                    data=data,
                                    file_type="title_card",
                                    id_key="episode_id",
                                    id_value=episode["id"],
                                ),
                            )
                            for episode in season["episodes"]
                        ],
                    )
                    for season in data["show"]["seasons"]
                ],
            )

        if data.get("movie"):
            movie = Movie(
                tmdb_id=data["movie"]["id"],
                name=data["movie"]["title"],
                year=int(data["movie"]["release_date"][:4])
                if data["movie"]["release_date"]
                else None,
                poster_id=self._get_file_id(
                    data=data, file_type="poster", id_key="movie_id", id_value=data["movie"]["id"]
                )
                or self._get_file_id(
                    data=data, file_type="poster", id_key="set_id", id_value=data["id"]
                ),
            )

        if data.get("collection"):
            collection = Collection(
                name=data["collection"]["collection_name"],
                poster_id=self._get_file_id(
                    data=data,
                    file_type="poster",
                    id_key="collection_id",
                    id_value=data["collection"]["id"],
                ),
                backdrop_id=next(
                    (x["id"] for x in data["files"] if x["fileType"] == "backdrop"), None
                ),
            )
            if include_movies:
                collection.movies = [
                    Movie(
                        tmdb_id=entry["id"],
                        name=entry["title"],
                        year=int(entry["release_date"][:4]) if entry["release_date"] else None,
                        poster_id=self._get_file_id(
                            data=data, file_type="poster", id_key="movie_id", id_value=entry["id"]
                        ),
                    )
                    for entry in data["collection"].get("movies", [])
                ]

        return MediuxSet(
            id=int(data["id"]), name=data["set_name"], show=show, movie=movie, collection=collection
        )

    def _download(self, endpoint: str, output: Path) -> None:
        try:
            response = get(
                f"{self.api_url}{endpoint}", headers=self.headers, timeout=self.timeout, stream=True
            )
            response.raise_for_status()

            total_length = int(response.headers.get("content-length", 0))
            chunk_size = 1024
            LOGGER.debug("Downloading %s", output)

            with Progress(console=CONSOLE) as progress:
                task = progress.add_task(
                    f"Downloading {output.relative_to(get_cache_root() / 'covers')}",
                    total=total_length,
                )
                with output.open("wb") as stream:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            stream.write(chunk)
                            progress.update(task, advance=len(chunk))
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s%s'", self.api_url, endpoint)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")

    def download_image(self, id: str, output_file: Path) -> None:  # noqa: A002
        self._download(endpoint=f"/assets/{id}", output=output_file)
