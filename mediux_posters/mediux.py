__all__ = ["Mediux", "MediuxSet", "Show", "Season", "Episode", "Movie"]

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from requests import get
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout
from rich.progress import Progress

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.utils import slugify

LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Episode:
    number: int
    name: str
    title_card_id: str | None = None


@dataclass(kw_only=True)
class Season:
    number: int
    name: str
    poster_id: str | None = None
    episodes: list[Episode]


@dataclass(kw_only=True)
class Show:
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


@dataclass(kw_only=True)
class Movie:
    name: str
    year: int | None = None
    poster_id: str | None = None

    @property
    def filename(self) -> str:
        if self.year:
            return f"{self.name} ({self.year})"
        return self.name


@dataclass(kw_only=True)
class Collection:
    name: str
    poster_id: str | None = None
    backdrop_id: str | None = None
    movies: list[Movie]


@dataclass(kw_only=True)
class MediuxSet:
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
    def __init__(self, timeout: int = 30):
        self.api_url = "https://api.mediux.pro"
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",  # noqa: E501
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "Windows",
        }

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

    def scrape_set(self, set_url: str) -> dict:
        if not set_url.startswith("https://mediux.pro/sets"):
            LOGGER.error("Invalid set link: %s", set_url)
            return {}

        LOGGER.info("Downloading set information for: %s", set_url)
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
                if x["fileType"] == file_type and x[id_key] and x[id_key]["id"] == id_value
            ),
            None,
        )

    def process_data(self, data: dict) -> MediuxSet:
        show, movie, collection = None, None, None

        if data.get("show"):
            show = Show(
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
                name=data["movie"]["title"],
                year=int(data["movie"]["release_date"][:4])
                if data["movie"]["release_date"]
                else None,
                poster_id=self._get_file_id(
                    data=data, file_type="poster", id_key="movie_id", id_value=data["movie"]["id"]
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
                movies=[
                    Movie(
                        name=entry["title"],
                        year=int(entry["release_date"][:4]) if entry["release_date"] else None,
                        poster_id=self._get_file_id(
                            data=data, file_type="poster", id_key="movie_id", id_value=entry["id"]
                        ),
                    )
                    for entry in data["collection"]["movies"]
                ],
            )

        return MediuxSet(
            id=int(data["id"]), name=data["set_name"], show=show, movie=movie, collection=collection
        )

    def _download_images(self, folder_path: Path, images: dict[str, str]) -> None:
        folder_path.mkdir(parents=True, exist_ok=True)
        for img_name, img_id in images.items():
            img_file = folder_path / f"{slugify(img_name)}.jpg"
            if img_id and not img_file.exists():
                self.download_image(id=img_id, output_file=img_file)

    def download_show_images(self, show: Show) -> None:
        cover_folder = get_cache_root() / "covers" / "shows" / slugify(show.filename)
        self._download_images(
            cover_folder, {"Poster": show.poster_id, "Backdrop": show.backdrop_id}
        )
        for season in show.seasons:
            self._download_images(cover_folder, {f"Season-{season.number:02d}": season.poster_id})
            for episode in season.episodes:
                self._download_images(
                    cover_folder,
                    {f"S{season.number:02d}E{episode.number:02d}": episode.title_card_id},
                )

    def download_movie_images(self, movie: Movie) -> None:
        cover_folder = get_cache_root() / "covers" / "movies" / slugify(movie.filename)
        self._download_images(cover_folder, {"Poster": movie.poster_id})

    def download_collection_images(self, collection: Collection) -> None:
        cover_folder = get_cache_root() / "covers" / "collections" / slugify(collection.name)
        self._download_images(
            cover_folder, {"Poster": collection.poster_id, "Backdrop": collection.backdrop_id}
        )
        for movie in collection.movies:
            self._download_images(cover_folder, {movie.filename: movie.poster_id})
