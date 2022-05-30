import attr
import pytest
from unittest import mock

import web_poet
import scrapy
from web_poet.exceptions import RequestBackendError
from tests.utils import AsyncMock

from scrapy_poet.backend import create_scrapy_backend


@pytest.fixture
def scrapy_backend():
    mock_backend = AsyncMock()
    return create_scrapy_backend(mock_backend)


@pytest.mark.asyncio
async def test_incompatible_request(scrapy_backend):
    """The Request must have fields that are a subset of `scrapy.Request`."""

    @attr.define
    class Request(web_poet.HttpRequest):
        incompatible_field: str = "value"

    req = Request("https://example.com")

    with pytest.raises(RequestBackendError):
        await scrapy_backend(req)


@pytest.mark.asyncio
async def test_incompatible_scrapy_request(scrapy_backend):
    """The Request must be web_poet.HttpRequest and not anything else."""

    req = scrapy.Request("https://example.com")

    with pytest.raises(TypeError):
        await scrapy_backend(req)


@pytest.fixture
def fake_http_response():
    return web_poet.HttpResponse(
        "https://example.com",
        b"some content",
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


@pytest.mark.asyncio
async def test_scrapy_poet_backend(fake_http_response):
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:

        mock_dtf.return_value = fake_http_response

        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        response = await scrapy_backend(req)

        mock_downloader.assert_called_once()
        assert isinstance(response, web_poet.HttpResponse)

        assert response.url == "https://example.com"
        assert response.text == "some content"
        assert response.status == 200
        assert response.headers.get("Content-Type") == "text/html; charset=utf-8"
        assert len(response.headers) == 1


@pytest.mark.asyncio
async def test_scrapy_poet_backend_ignored_request():
    """It should handle IgnoreRequest from Scrapy according to the web poet
    standard on additional request error handling."""
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.side_effect = scrapy.exceptions.IgnoreRequest
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        with pytest.raises(web_poet.exceptions.HttpError):
            await scrapy_backend(req)
