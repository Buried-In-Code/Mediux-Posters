__all__ = ["Mediux"]

import json
import logging
from json import JSONDecodeError
from pathlib import Path

from bs4 import BeautifulSoup
from requests import get
from requests.exceptions import ConnectionError, HTTPError, ReadTimeout  # noqa: A004
from rich.progress import Progress

from mediux_posters import get_cache_root
from mediux_posters.console import CONSOLE
from mediux_posters.services._base import (
    BaseCollection,
    BaseEpisode,
    BaseMovie,
    BaseSeason,
    BaseShow,
)
from mediux_posters.utils import MediaType, slugify

LOGGER = logging.getLogger(__name__)


def parse_to_dict(input_string: str) -> dict:
    try:
        clean_string = input_string.replace('\\\\\\"', "").replace("\\", "").replace("u0026", "&")
        json_data = clean_string[clean_string.find("{") : clean_string.rfind("}") + 1]
        return json.loads(json_data) if json_data else {}
    except JSONDecodeError:
        return {}


def _get_file_id(data: dict, file_type: str, id_key: str, id_value: str) -> str | None:
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

    def scrape_set(self, set_id: int) -> dict:
        set_url = f"{self.web_url}/sets/{set_id}"

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

    def _download(self, endpoint: str, output: Path) -> bool:
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
            return True
        except ConnectionError:
            LOGGER.error("Unable to connect to '%s%s'", self.api_url, endpoint)
        except HTTPError as err:
            LOGGER.error(err.response.text)
        except ReadTimeout:
            LOGGER.error("Service took too long to respond")
        return False

    def _download_image(
        self,
        obj: BaseShow | BaseSeason | BaseEpisode | BaseMovie | BaseCollection,
        filename: str,
        image_id: str,
    ) -> Path | None:
        poster_path = (
            get_cache_root()
            / "covers"
            / obj.mediatype.value
            / slugify(obj.display_name)
            / f"{slugify(filename)}.jpg"
        )
        if poster_path.exists():
            return poster_path
        poster_path.parent.mkdir(parents=True, exist_ok=True)
        if self._download(endpoint=f"/assets/{image_id}", output=poster_path):
            return poster_path
        return None

    def download_show_posters(self, data: dict, show: BaseShow) -> None:
        if poster_id := _get_file_id(
            data=data, file_type="poster", id_key="show_id", id_value=str(show.tmdb_id)
        ):
            show.poster = self._download_image(obj=show, filename="Poster", image_id=poster_id)
        if backdrop_id := _get_file_id(
            data=data, file_type="backdrop", id_key="show_id_backdrop", id_value=str(show.tmdb_id)
        ):
            show.backdrop = self._download_image(
                obj=show, filename="Backdrop", image_id=backdrop_id
            )

        for season in show.seasons:
            season_data = next(
                iter(
                    x
                    for x in data.get("show", {}).get("seasons", [])
                    if int(x.get("season_number", "-1")) == season.number
                ),
                None,
            )
            if not season_data:
                LOGGER.warning(
                    "[%s] Unable to find '%s S%02d'",
                    type(self).__name__,
                    show.display_name,
                    season.number,
                )
                continue
            if poster_id := _get_file_id(
                data=data, file_type="poster", id_key="season_id", id_value=season_data.get("id")
            ):
                season.poster = self._download_image(
                    obj=show, filename=f"S{season.number:02}", image_id=poster_id
                )

            for episode in season.episodes:
                episode_data = next(
                    iter(
                        x
                        for x in season_data.get("episodes", [])
                        if int(x.get("episode_number", "-1")) == episode.number
                    ),
                    None,
                )
                if not episode_data:
                    LOGGER.warning(
                        "[%s] Unable to find '%s S%02dE%02d'",
                        type(self).__name__,
                        show.display_name,
                        season.number,
                        episode.number,
                    )
                    continue
                if title_card_id := _get_file_id(
                    data=data,
                    file_type="title_card",
                    id_key="episode_id",
                    id_value=episode_data.get("id"),
                ):
                    episode.title_card = self._download_image(
                        obj=show,
                        filename=f"S{season.number:02}E{episode.number:02}",
                        image_id=title_card_id,
                    )

    def download_movie_posters(self, data: dict, movie: BaseMovie) -> None:
        if poster_id := _get_file_id(
            data=data, file_type="poster", id_key="movie_id", id_value=str(movie.tmdb_id)
        ):
            movie.poster = self._download_image(obj=movie, filename="Poster", image_id=poster_id)
        if backdrop_id := _get_file_id(
            data=data, file_type="backdrop", id_key="movie_id_backdrop", id_value=str(movie.tmdb_id)
        ):
            movie.backdrop = self._download_image(
                obj=movie, filename="Backdrop", image_id=backdrop_id
            )

    def download_collection_posters(self, data: dict, collection: BaseCollection) -> None:
        if poster_id := _get_file_id(
            data=data, file_type="poster", id_key="collection_id", id_value=str(collection.tmdb_id)
        ):
            collection.poster = self._download_image(
                obj=collection, filename="Poster", image_id=poster_id
            )
        if backdrop_id := next(
            (x["id"] for x in data["files"] if x["fileType"] == "backdrop"), None
        ):
            collection.backdrop = self._download_image(
                obj=collection, filename="Backdrop", image_id=backdrop_id
            )

    def list_sets(self, mediatype: MediaType, tmdb_id: int) -> list[dict]:
        if mediatype == MediaType.SHOW:
            url = f"{self.web_url}/shows/{tmdb_id}"
        elif mediatype == MediaType.MOVIE:
            url = f"{self.web_url}/movies/{tmdb_id}"
        elif mediatype == MediaType.COLLECTION:
            url = f"{self.web_url}/collections/{tmdb_id}"
        else:
            raise TypeError("Unknown Mediatype")
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
            if "files" in script.text and "sets" in script.text:
                return parse_to_dict(script.text).get("sets", [])
        return []
