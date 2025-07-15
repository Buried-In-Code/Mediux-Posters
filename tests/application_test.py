from unittest.mock import MagicMock, patch

import pytest

from mediux_posters.__main__ import MAX_IMAGE_SIZE, process_set_data
from mediux_posters.mediux import Mediux
from mediux_posters.mediux.schemas import MovieSet as SetData
from mediux_posters.services._base.schemas import BaseMovie as Media
from mediux_posters.services._base.service import BaseService
from mediux_posters.services.service_cache import ServiceCache


@pytest.fixture
def mock_services() -> tuple[Mediux, BaseService]:
    mediux: Mediux = MagicMock(spec=Mediux)
    service: BaseService = MagicMock(spec=BaseService)
    service_cache: ServiceCache = MagicMock(spec=ServiceCache)
    service_cache.select.return_value = None
    service.cache = service_cache
    return mediux, service


@pytest.mark.parametrize(
    ("max_size", "should_warn"),
    [(MAX_IMAGE_SIZE + 1, True), (MAX_IMAGE_SIZE, True), (MAX_IMAGE_SIZE - 1, False)],
)
def test_image_size_warning_threshold(
    media_obj: Media,
    set_data: SetData,
    mock_services: tuple[Mediux, BaseService],
    max_size: int,
    should_warn: bool,
) -> None:
    mediux, service = mock_services

    image_file = MagicMock()
    image_file.stat.return_value.st_size = max_size

    with (
        patch("mediux_posters.__main__.get_cached_image", return_value=image_file),
        patch("mediux_posters.__main__.LOGGER") as mock_logger,
    ):
        process_set_data(
            entry=media_obj,
            set_data=set_data,
            mediux=mediux,
            service=service,
            priority_usernames=[],
        )
        if should_warn:
            mock_logger.warning.assert_called_once()
        else:
            mock_logger.warning.assert_not_called()
