import attr
import pytest
from unittest import mock

import web_poet
import scrapy
import twisted
from pytest_twisted import ensureDeferred, inlineCallbacks
from scrapy import Spider
from tests.utils import AsyncMock
from web_poet import HttpClient
from web_poet.pages import ItemWebPage

from scrapy_poet.backend import create_scrapy_backend
from tests.utils import (
    crawl_single_item, make_crawler, HtmlResource, MockServer
)


@pytest.fixture
def scrapy_backend():
    mock_backend = AsyncMock()
    return create_scrapy_backend(mock_backend)


@ensureDeferred
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


@ensureDeferred
async def test_scrapy_poet_backend(fake_http_response):
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.maybe_deferred_to_future", new_callable=AsyncMock
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


@ensureDeferred
async def test_scrapy_poet_backend_ignored_request():
    """It should handle IgnoreRequest from Scrapy according to the web poet
    standard on additional request error handling."""
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.side_effect = scrapy.exceptions.IgnoreRequest
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        with pytest.raises(web_poet.exceptions.HttpError):
            await scrapy_backend(req)


@ensureDeferred
async def test_scrapy_poet_backend_twisted_error():
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.side_effect = twisted.internet.error.TimeoutError
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        with pytest.raises(web_poet.exceptions.HttpRequestError):
            await scrapy_backend(req)


@ensureDeferred
async def test_scrapy_poet_backend_head_redirect(fake_http_response):
    req = web_poet.HttpRequest("https://example.com", method="HEAD")

    with mock.patch(
        "scrapy_poet.backend.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.return_value = fake_http_response
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        await scrapy_backend(req)

        args, kwargs = mock_downloader.call_args
        scrapy_request = args[0]
        assert scrapy_request.meta.get("dont_redirect") is True


@ensureDeferred
async def test_scrapy_poet_backend_dont_filter(fake_http_response):
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.backend.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.return_value = fake_http_response
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_backend = create_scrapy_backend(mock_downloader)

        await scrapy_backend(req)

        args, kwargs = mock_downloader.call_args
        scrapy_request = args[0]
        assert scrapy_request.dont_filter is True


@inlineCallbacks
def test_scrapy_poet_backend_await():
    """Make sure that the awaiting of the backend call works.

    For this test to pass, the resulting deferred must be awaited as such when
    using a non-asyncio Twisted reactor, but first converted into a future
    when using an asyncio Twisted reactor.
    """
    items = []
    with MockServer(HtmlResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                await self.http_client.request(server.root_url)
                return {'foo': 'bar'}


        class TestSpider(Spider):
            name = 'test_spider'
            start_urls = [server.root_url]

            custom_settings = {
                'DOWNLOADER_MIDDLEWARES': {
                    'scrapy_poet.InjectionMiddleware': 543,
                },
            }

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()
        assert items == [{'foo': 'bar'}]
