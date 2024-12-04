__all__ = ["Constants"]

import logging
from functools import lru_cache

from plexapi.exceptions import Unauthorized
from typer import Abort

from mediux_posters.mediux import Mediux
from mediux_posters.services.jellyfin import Jellyfin
from mediux_posters.services.plex import Plex
from mediux_posters.settings import Settings

LOGGER = logging.getLogger(__name__)


class Constants:
    _jellyfin: Jellyfin | None = None
    _mediux: Mediux | None = None
    _plex: Plex | None = None
    _settings: Settings | None = None

    @staticmethod
    @lru_cache(maxsize=1)
    def settings() -> Settings:
        if Constants._settings is None:
            Constants._settings = Settings.load()
            Constants._settings.save()
        return Constants._settings

    @staticmethod
    @lru_cache(maxsize=1)
    def jellyfin() -> Jellyfin:
        if Constants._jellyfin is None:
            settings = Constants.settings()
            if not settings.jellyfin.token or not settings.jellyfin.username:
                LOGGER.error("This command requires a Jellyfin token and username to be set")
                raise Abort
            Constants._jellyfin = Jellyfin(settings=settings.jellyfin)
        return Constants._jellyfin

    @staticmethod
    @lru_cache(maxsize=1)
    def plex() -> Plex:
        if Constants._plex is None:
            settings = Constants.settings()
            try:
                if not settings.plex.token:
                    LOGGER.error("This command requires a Plex Token to be set")
                    raise Abort
                Constants._plex = Plex(settings=settings.plex)
            except Unauthorized as err:
                LOGGER.error(err)
                raise Abort from err
        return Constants._plex

    @staticmethod
    @lru_cache(maxsize=1)
    def mediux() -> Mediux:
        if Constants._mediux is None:
            Constants._mediux = Mediux()
        return Constants._mediux
