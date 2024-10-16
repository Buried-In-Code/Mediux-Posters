__all__ = ["Mediux", "MediuxSet", "Show", "Season", "Episode", "Movie"]

import contextlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from requests import RequestException, get
from rich.progress import Progress

from mediux_posters import get_project_root

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
    year: int
    poster_id: str | None = None
    backdrop_id: str | None = None
    seasons: list[Season]

    @property
    def filename(self) -> str:
        return f"{self.name} ({self.year})"


@dataclass(kw_only=True)
class Movie:
    name: str
    year: int
    poster_id: str | None = None

    @property
    def filename(self) -> str:
        return f"{self.name} ({self.year})"


@dataclass(kw_only=True)
class MediuxSet:
    id: int
    name: str
    show: Show | None = None
    movies: list[Movie] = field(default_factory=list)
    poster_id: str | None = None
    backdrop_id: str | None = None


def parse_to_dict(input_string: str) -> dict:
    input_string = input_string.replace('\\\\\\"', "")
    input_string = input_string.replace("\\", "")
    input_string = input_string.replace("u0026", "&")

    json_start_index = input_string.find("{")
    json_end_index = input_string.rfind("}")
    json_data = input_string[json_start_index : json_end_index + 1]

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

            with Progress() as progress:
                task = progress.add_task(
                    f"Downloading {output.relative_to(get_project_root())}", total=total_length
                )

                with output.open("wb") as stream:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            stream.write(chunk)
                            progress.update(task, advance=len(chunk))
        except RequestException:
            LOGGER.exception("")

    def download_image(self, id: str, output_file: Path) -> None:  # noqa: A002
        self._download(endpoint=f"/assets/{id}", output=output_file)

    def scrape_pages(self, url: str, page: int = 1) -> list[dict]:
        LOGGER.info("Downloading page: %d", page)
        response = get(url, params={"page": page}, timeout=30)
        if response.status_code not in (200, 500):
            LOGGER.error(response.text)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.find_all("script"):
            if "files" in script.text and "set" in script.text and "Set Link\\" not in script.text:
                try:
                    return parse_to_dict(script.text)["children"][2][3]["children"][3]["sets"]
                except IndexError:
                    return []
        return []

    def scrape_author(self, author: str) -> list[dict]:
        LOGGER.info("Downloading author information for: %s", author)
        page = 1
        output = self.scrape_pages(url=f"https://mediux.pro/user/{author}/sets")
        results = []
        while output:
            results.extend(output)
            page += 1
            output = self.scrape_pages(url=f"https://mediux.pro/user/{author}/sets", page=page)
        return results

    def scrape_set(self, set_url: str) -> dict:
        if not set_url.startswith("https://mediux.pro/sets"):
            LOGGER.error("Invalid set link: %s", set_url)
            return {}
        LOGGER.info("Downloading set information for: %s", set_url)
        response = get(set_url, timeout=30)
        if response.status_code != 200 and (
            response.status_code != 500 or "mediux.pro" not in set_url
        ):
            LOGGER.error(response.text)
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup.find_all("script"):
            if "files" in script.text and "set" in script.text and "Set Link\\" not in script.text:
                return parse_to_dict(script.text)["set"]
        return {}

    def process_data(self, data: dict) -> MediuxSet:
        show = None
        movies = []
        collection_poster_id = None
        collection_backdrop_id = None
        if data.get("show"):
            seasons = []
            for season in data["show"]["seasons"]:
                episodes = []
                for episode in season["episodes"]:
                    title_card_id = None
                    if title_card := next(
                        iter(
                            [
                                x
                                for x in data["files"]
                                if x["fileType"] == "title_card"
                                and x["episode_id"]
                                and x["episode_id"]["id"] == episode["id"]
                            ]
                        ),
                        None,
                    ):
                        title_card_id = title_card["id"]
                    episodes.append(
                        Episode(
                            number=int(episode["episode_number"]),
                            name=episode["episode_name"],
                            title_card_id=title_card_id,
                        )
                    )

                poster_id = None
                if poster := next(
                    iter(
                        [
                            x
                            for x in data["files"]
                            if x["fileType"] == "poster"
                            and x["season_id"]
                            and x["season_id"]["id"] == season["id"]
                        ]
                    ),
                    None,
                ):
                    poster_id = poster["id"]
                seasons.append(
                    Season(
                        number=int(season["season_number"]),
                        name=season["name"],
                        poster_id=poster_id,
                        episodes=episodes,
                    )
                )

            poster_id = None
            if poster := next(
                iter([x for x in data["files"] if x["fileType"] == "poster" and x["show_id"]]), None
            ):
                poster_id = poster["id"]
            backdrop_id = None
            if backdrop := next(
                iter(
                    [
                        x
                        for x in data["files"]
                        if x["fileType"] == "backdrop" and x["show_id_backdrop"]
                    ]
                ),
                None,
            ):
                backdrop_id = backdrop["id"]
            with contextlib.suppress(TypeError):
                show = Show(
                    name=data["show"]["name"],
                    year=int(data["show"]["first_air_date"][:4]),
                    poster_id=poster_id,
                    backdrop_id=backdrop_id,
                    seasons=seasons,
                )
        elif data.get("collection"):
            collection_poster_id = None
            if collection_poster := next(
                iter(
                    [
                        x
                        for x in data["files"]
                        if x["fileType"] == "poster"
                        and x["collection_id"]
                        and x["collection_id"]["id"] == data["collection"]["id"]
                    ]
                ),
                None,
            ):
                collection_poster_id = collection_poster["id"]
            collection_backdrop_id = None
            if collection_backdrop := next(
                iter([x for x in data["files"] if x["fileType"] == "backdrop"]), None
            ):
                collection_backdrop_id = collection_backdrop["id"]
            for entry in data["collection"]["movies"]:
                poster_id = None
                if poster := next(
                    iter(
                        [
                            x
                            for x in data["files"]
                            if x["fileType"] == "poster"
                            and x["movie_id"]
                            and x["movie_id"]["id"] == entry["id"]
                        ]
                    ),
                    None,
                ):
                    poster_id = poster["id"]
                with contextlib.suppress(TypeError):
                    movies.append(
                        Movie(
                            name=entry["title"],
                            year=int(entry["release_date"][:4]),
                            poster_id=poster_id,
                        )
                    )
        elif data.get("movie"):
            poster_id = None
            if poster := next(
                iter(
                    [
                        x
                        for x in data["files"]
                        if x["fileType"] == "poster"
                        and x["movie_id"]
                        and x["movie_id"]["id"] == data["movie"]["id"]
                    ]
                ),
                None,
            ):
                poster_id = poster["id"]
            with contextlib.suppress(TypeError):
                movies.append(
                    Movie(
                        name=data["movie"]["title"],
                        year=int(data["movie"]["release_date"][:4]),
                        poster_id=poster_id,
                    )
                )
        return MediuxSet(
            id=int(data["id"]),
            name=data["set_name"],
            show=show,
            movies=movies,
            poster_id=collection_poster_id,
            backdrop_id=collection_backdrop_id,
        )

    def download_set_images(self, data: MediuxSet) -> None:
        cover_folder = get_project_root() / "covers" / "show" / data.show.filename
        cover_folder.mkdir(parents=True, exist_ok=True)

        poster_file = cover_folder / "Poster.jpg"
        if data.show.poster_id and not poster_file.exists():
            self.download_image(id=data.show.poster_id, output_file=poster_file)
        backdrop_file = cover_folder / "Backdrop.jpg"
        if data.show.backdrop_id and not backdrop_file.exists():
            self.download_image(id=data.show.backdrop_id, output_file=backdrop_file)

        for season in data.show.seasons:
            season_poster_file = cover_folder / f"Season-{season.number:02d}.jpg"
            if season.poster_id and not season_poster_file.exists():
                self.download_image(id=season.poster_id, output_file=season_poster_file)

            for episode in season.episodes:
                episode_title_card_file = (
                    cover_folder / f"S{season.number:02d}E{episode.number:02d}.jpg"
                )
                if episode.title_card_id and not episode_title_card_file.exists():
                    self.download_image(
                        id=episode.title_card_id, output_file=episode_title_card_file
                    )

    def download_collection_images(self, folder_name: str, data: MediuxSet) -> None:
        cover_folder = get_project_root() / "covers" / "movie" / folder_name
        cover_folder.mkdir(parents=True, exist_ok=True)

        poster_file = cover_folder / "Poster.jpg"
        if data.poster_id and not poster_file.exists():
            self.download_image(id=data.poster_id, output_file=poster_file)
        backdrop_file = cover_folder / "Backdrop.jpg"
        if data.backdrop_id and not backdrop_file.exists():
            self.download_image(id=data.backdrop_id, output_file=backdrop_file)

    def download_movie_image(self, folder_name: str, movie: Movie) -> None:
        cover_folder = get_project_root() / "covers" / "movie" / folder_name
        cover_folder.mkdir(parents=True, exist_ok=True)

        poster_file = cover_folder / f"{movie.filename}.jpg"
        if movie.poster_id and not poster_file.exists():
            self.download_image(id=movie.poster_id, output_file=poster_file)
