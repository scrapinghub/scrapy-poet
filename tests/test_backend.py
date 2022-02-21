import attr
import pytest
from unittest import mock

import web_poet
import scrapy
from scrapy_poet.backend import scrapy_downloader_var
from scrapy_poet.backend import scrapy_poet_backend, RequestBackendError


class AsyncMock(mock.MagicMock):
    """workaround since python 3.7 doesn't ship with asyncmock."""

    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


@pytest.mark.asyncio
async def test_scrapy_poet_backend_var_unset():
    """The ContextVar must be set first."""
    req = web_poet.Request("https://example.com")

    with pytest.raises(LookupError):
        await scrapy_poet_backend(req)


@pytest.mark.asyncio
async def test_scrapy_poet_backend_incompatible_request():
    """The Request must have fields that are a subset of `scrapy.Request`."""

    @attr.define
    class Request(web_poet.Request):
        incompatible_field: str = "value"

    req = Request("https://example.com")

    with pytest.raises(RequestBackendError):
        await scrapy_poet_backend(req)


@pytest.mark.asyncio
async def test_scrapy_poet_backend():
    req = web_poet.Request("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:

        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_downloader_var.set(mock_downloader)

        response = await scrapy_poet_backend(req)

        mock_downloader.assert_called_once()
        assert isinstance(response, web_poet.ResponseData)


@pytest.mark.asyncio
async def test_scrapy_poet_backend_ignored_request():
    """It should handle IgnoreRequest from Scrapy gracefully."""
    req = web_poet.Request("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:

        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        mock_downloader.side_effect = scrapy.exceptions.IgnoreRequest
        scrapy_downloader_var.set(mock_downloader)

        await scrapy_poet_backend(req)
