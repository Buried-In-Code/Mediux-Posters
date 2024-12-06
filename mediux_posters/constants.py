__all__ = ["Constants"]

import logging

from plexapi.exceptions import Unauthorized

from mediux_posters.mediux import Mediux
from mediux_posters.services import BaseService
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
    def settings() -> Settings:
        if Constants._settings is None:
            Constants._settings = Settings.load()
            Constants._settings.save()
        return Constants._settings

    @staticmethod
    def jellyfin() -> Jellyfin | None:
        if Constants._jellyfin is None:
            settings = Constants.settings()
            if not settings.jellyfin.token or not settings.jellyfin.username:
                return None
            Constants._jellyfin = Jellyfin(settings=settings.jellyfin)
        return Constants._jellyfin

    @staticmethod
    def plex() -> Plex | None:
        if Constants._plex is None:
            settings = Constants.settings()
            try:
                if not settings.plex.token:
                    return None
                Constants._plex = Plex(settings=settings.plex)
            except Unauthorized as err:
                LOGGER.warning(err)
                return None
        return Constants._plex

    @staticmethod
    def service_list() -> list[BaseService]:
        output = []
        if Constants.jellyfin():
            output.append(Constants.jellyfin())
        if Constants.plex():
            output.append(Constants.plex())
        return output

    @staticmethod
    def mediux() -> Mediux:
        if Constants._mediux is None:
            Constants._mediux = Mediux()
        return Constants._mediux
