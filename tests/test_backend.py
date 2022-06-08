import attr
from functools import partial
from unittest import mock

import pytest
import scrapy
import twisted
import web_poet
from pytest_twisted import ensureDeferred, inlineCallbacks
from scrapy import Request, Spider
from scrapy.exceptions import IgnoreRequest
from tests.utils import AsyncMock
from twisted.internet import reactor
from twisted.internet.task import deferLater
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from web_poet import HttpClient
from web_poet.exceptions import HttpError, HttpRequestError, HttpResponseError
from web_poet.pages import ItemWebPage

from scrapy_poet.backend import create_scrapy_backend
from scrapy_poet.utils import http_request_to_scrapy_request
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


class LeafResource(Resource):
    isLeaf = True

    def deferRequest(self, request, delay, f, *a, **kw):
        def _cancelrequest(_):
            # silence CancelledError
            d.addErrback(lambda _: None)
            d.cancel()

        d = deferLater(reactor, delay, f, *a, **kw)
        request.notifyFinish().addErrback(_cancelrequest)
        return d


class EchoResource(LeafResource):
    def render_GET(self, request):
        return request.content.read()


@inlineCallbacks
def test_additional_requests_success():
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                response = await self.http_client.request(
                    server.root_url,
                    body=b'bar',
                )
                return {'foo': response.body.decode()}

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


class StatusResource(LeafResource):
    def render_GET(self, request):
        decoded_body = request.content.read().decode()
        if decoded_body:
            request.setResponseCode(int(decoded_body))
        return b""


@inlineCallbacks
def test_additional_requests_bad_response():
    items = []

    with MockServer(StatusResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                try:
                    await self.http_client.request(
                        server.root_url,
                        body=b'400',
                    )
                except HttpResponseError:
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


class DelayedResource(LeafResource):
    def render_GET(self, request):
        decoded_body = request.content.read().decode()
        seconds = float(decoded_body) if decoded_body else 0
        self.deferRequest(
            request,
            seconds,
            self._delayedRender,
            request,
            seconds,
        )
        return NOT_DONE_YET

    def _delayedRender(self, request, seconds):
        request.finish()


@inlineCallbacks
def test_additional_requests_connection_issue():
    items = []

    with mock.patch('scrapy_poet.backend.http_request_to_scrapy_request') \
            as mock_http_request_to_scrapy_request:
        mock_http_request_to_scrapy_request.side_effect = partial(
            http_request_to_scrapy_request,
            meta={'download_timeout': 0.001},
        )

        with MockServer(DelayedResource) as server:

            @attr.define
            class ItemPage(ItemWebPage):
                http_client: HttpClient

                async def to_item(self):
                    try:
                        await self.http_client.request(
                            server.root_url,
                            body=b"0.002",
                        )
                    except HttpRequestError:
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


@inlineCallbacks
def test_additional_requests_ignored_request():
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                try:
                    await self.http_client.request(
                        server.root_url,
                        body=b'ignore',
                    )
                except HttpError as e:
                    return {'exc': e.__class__}

        class TestDownloaderMiddleware:
            def process_response(self, request, response, spider):
                if b'ignore' in response.body:
                    raise IgnoreRequest
                return response

        class TestSpider(Spider):
            name = 'test_spider'
            start_urls = [server.root_url]

            custom_settings = {
                'DOWNLOADER_MIDDLEWARES': {
                    TestDownloaderMiddleware: 1,
                    'scrapy_poet.InjectionMiddleware': 543,
                },
            }

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{'exc': HttpError}]


@pytest.mark.xfail(
    reason=(
        "Currently, we do not make a distinction between exceptions raised "
        "from the downloader or from a downloader middleware, except for "
        "IgnoreRequest. In the future, we might want to inspect the stack to "
        "determine the source of an exception and raise HttpError instead of "
        "HttpRequestError when the exception originates in a downloader "
        "middleware."
    ),
    strict=True,
)
@inlineCallbacks
def test_additional_requests_unhandled_downloader_middleware_exception():
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                try:
                    await self.http_client.request(
                        server.root_url,
                        body=b'raise',
                    )
                except HttpError as e:
                    return {'exc': e.__class__}

        class TestDownloaderMiddleware:
            def process_response(self, request, response, spider):
                if b'raise' in response.body:
                    raise RuntimeError
                return response

        class TestSpider(Spider):
            name = 'test_spider'
            start_urls = [server.root_url]

            custom_settings = {
                'DOWNLOADER_MIDDLEWARES': {
                    TestDownloaderMiddleware: 1,
                    'scrapy_poet.InjectionMiddleware': 543,
                },
            }

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{'exc': HttpError}]


@inlineCallbacks
def test_additional_requests_dont_filter():
    """Verify that while duplicate regular requests are filtered out,
    additional requests are not (neither relative to the main requests not
    relative to each other).

    In Scrapy, request de-duplication is implemented on the scheduler, and
    because additional requests do not go through the scheduler, this works as
    expected.
    """
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(ItemWebPage):
            http_client: HttpClient

            async def to_item(self):
                response1 = await self.http_client.request(
                    server.root_url,
                    body=b'a',
                )
                response2 = await self.http_client.request(
                    server.root_url,
                    body=b'a',
                )
                return {response1.body.decode(): response2.body.decode()}

        class TestSpider(Spider):
            name = 'test_spider'

            custom_settings = {
                'DOWNLOADER_MIDDLEWARES': {
                    'scrapy_poet.InjectionMiddleware': 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, body=b'a')
                yield Request(server.root_url, body=b'a')

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{'a': 'a'}]
