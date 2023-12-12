import sys
import warnings
from functools import partial
from typing import Any, Callable, List, Optional, Sequence, Set
from unittest import mock

import attr
import pytest
import scrapy
import twisted
import web_poet
from pytest_twisted import ensureDeferred, inlineCallbacks
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response
from scrapy.utils.defer import maybe_deferred_to_future
from web_poet import BrowserResponse, HttpClient
from web_poet.exceptions import HttpError, HttpRequestError, HttpResponseError
from web_poet.pages import WebPage

from scrapy_poet import DummyResponse, PageObjectInputProvider
from scrapy_poet.downloader import create_scrapy_downloader
from scrapy_poet.utils import (
    NO_CALLBACK,
    http_request_to_scrapy_request,
    is_min_scrapy_version,
)
from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import (
    AsyncMock,
    DelayedResource,
    EchoResource,
    StatusResource,
    make_crawler,
)


@pytest.fixture
def scrapy_downloader() -> Callable:
    mock_downloader = AsyncMock()
    return create_scrapy_downloader(mock_downloader)


@ensureDeferred
async def test_incompatible_scrapy_request(scrapy_downloader) -> None:
    """The Request must be web_poet.HttpRequest and not anything else."""

    req = scrapy.Request("https://example.com")

    with pytest.raises(TypeError):
        await scrapy_downloader(req)


@pytest.fixture
def fake_http_response() -> web_poet.HttpResponse:
    return web_poet.HttpResponse(
        "https://example.com",
        b"some content",
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


@ensureDeferred
async def test_scrapy_poet_downloader(fake_http_response) -> None:
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.downloader.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:

        mock_dtf.return_value = fake_http_response

        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_downloader = create_scrapy_downloader(mock_downloader)

        response = await scrapy_downloader(req)

        mock_downloader.assert_called_once()
        assert isinstance(response, web_poet.HttpResponse)

        assert str(response.url) == "https://example.com"
        assert response.text == "some content"
        assert response.status == 200
        assert response.headers.get("Content-Type") == "text/html; charset=utf-8"
        assert len(response.headers) == 1


@ensureDeferred
async def test_scrapy_poet_downloader_ignored_request() -> None:
    """It should handle IgnoreRequest from Scrapy according to the web poet
    standard on additional request error handling."""
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.downloader.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.side_effect = scrapy.exceptions.IgnoreRequest
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_downloader = create_scrapy_downloader(mock_downloader)

        with pytest.raises(web_poet.exceptions.HttpError):
            await scrapy_downloader(req)


@ensureDeferred
async def test_scrapy_poet_downloader_twisted_error() -> None:
    req = web_poet.HttpRequest("https://example.com")

    with mock.patch(
        "scrapy_poet.downloader.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.side_effect = twisted.internet.error.TimeoutError
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_downloader = create_scrapy_downloader(mock_downloader)

        with pytest.raises(web_poet.exceptions.HttpRequestError):
            await scrapy_downloader(req)


@ensureDeferred
async def test_scrapy_poet_downloader_head_redirect(fake_http_response) -> None:
    req = web_poet.HttpRequest("https://example.com", method="HEAD")

    with mock.patch(
        "scrapy_poet.downloader.maybe_deferred_to_future", new_callable=AsyncMock
    ) as mock_dtf:
        mock_dtf.return_value = fake_http_response
        mock_downloader = mock.MagicMock(return_value=AsyncMock)
        scrapy_downloader = create_scrapy_downloader(mock_downloader)

        await scrapy_downloader(req)

        args, kwargs = mock_downloader.call_args
        scrapy_request = args[0]
        assert scrapy_request.meta.get("dont_redirect") is True


@inlineCallbacks
def test_additional_requests_success() -> None:
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(WebPage):
            http: HttpClient

            async def to_item(self):
                response = await self.http.request(
                    server.root_url,
                    body=b"bar",
                )
                return {"foo": response.body.decode()}

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    "scrapy_poet.InjectionMiddleware": 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]


@inlineCallbacks
def test_additional_requests_bad_response() -> None:
    items = []

    with MockServer(StatusResource) as server:

        @attr.define
        class ItemPage(WebPage):
            http: HttpClient

            async def to_item(self):
                try:
                    await self.http.request(
                        server.root_url,
                        body=b"400",
                    )
                except HttpResponseError:
                    return {"foo": "bar"}

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    "scrapy_poet.InjectionMiddleware": 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]


@inlineCallbacks
def test_additional_requests_connection_issue() -> None:
    items = []

    with mock.patch(
        "scrapy_poet.downloader.http_request_to_scrapy_request"
    ) as mock_http_request_to_scrapy_request:
        mock_http_request_to_scrapy_request.side_effect = partial(
            http_request_to_scrapy_request,
            meta={"download_timeout": 0.001},
        )

        with MockServer(DelayedResource) as server:

            @attr.define
            class ItemPage(WebPage):
                http: HttpClient

                async def to_item(self):
                    try:
                        await self.http.request(
                            server.root_url,
                            body=b"0.002",
                        )
                    except HttpRequestError:
                        return {"foo": "bar"}

            class TestSpider(Spider):
                name = "test_spider"

                custom_settings = {
                    "DOWNLOADER_MIDDLEWARES": {
                        "scrapy_poet.InjectionMiddleware": 543,
                    },
                }

                def start_requests(self):
                    yield Request(server.root_url, callback=self.parse)

                async def parse(self, response, page: ItemPage):
                    item = await page.to_item()
                    items.append(item)

            crawler = make_crawler(TestSpider, {})
            yield crawler.crawl()

    assert items == [{"foo": "bar"}]


@inlineCallbacks
def test_additional_requests_ignored_request() -> None:
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(WebPage):
            http: HttpClient

            async def to_item(self):
                try:
                    await self.http.request(
                        server.root_url,
                        body=b"ignore",
                    )
                except HttpError as e:
                    return {"exc": e.__class__}

        class TestDownloaderMiddleware:
            def process_response(self, request, response, spider):
                if b"ignore" in response.body:
                    raise IgnoreRequest
                return response

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    TestDownloaderMiddleware: 1,
                    "scrapy_poet.InjectionMiddleware": 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"exc": HttpError}]


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
def test_additional_requests_unhandled_downloader_middleware_exception() -> None:
    items = []

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(WebPage):
            http: HttpClient

            async def to_item(self):
                try:
                    await self.http.request(
                        server.root_url,
                        body=b"raise",
                    )
                except HttpError as e:
                    return {"exc": e.__class__}

        class TestDownloaderMiddleware:
            def process_response(self, request, response, spider):
                if b"raise" in response.body:
                    raise RuntimeError
                return response

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    TestDownloaderMiddleware: 1,
                    "scrapy_poet.InjectionMiddleware": 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"exc": HttpError}]


@inlineCallbacks
def test_additional_requests_dont_filter() -> None:
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
        class ItemPage(WebPage):
            http: HttpClient

            async def to_item(self):
                response1 = await self.http.request(
                    server.root_url,
                    body=b"a",
                )
                response2 = await self.http.request(
                    server.root_url,
                    body=b"a",
                )
                return {response1.body.decode(): response2.body.decode()}

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    "scrapy_poet.InjectionMiddleware": 543,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, body=b"a", callback=self.parse)
                yield Request(server.root_url, body=b"a", callback=self.parse)

            async def parse(self, response, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"a": "a"}]


@inlineCallbacks
def test_additional_requests_no_cb_deps() -> None:
    # https://github.com/scrapy-plugins/scrapy-zyte-api/issues/135
    # This tests that the additional request doesn't go through dep resolving
    # like if it used self.parse as a callback.

    items = []
    provider_calls = 0

    class BrowserResponseProvider(PageObjectInputProvider):
        provided_classes = {BrowserResponse}

        async def __call__(
            self, to_provide: Set[Callable], request: Request, crawler: Crawler
        ) -> Sequence[Any]:
            nonlocal provider_calls
            provider_calls += 1
            custom_request = Request(
                request.url, body=request.body, callback=NO_CALLBACK
            )
            scrapy_response: Response = await maybe_deferred_to_future(
                crawler.engine.download(custom_request)
            )
            result = BrowserResponse(
                url=scrapy_response.url,
                html=scrapy_response.text,
                status=scrapy_response.status,
            )
            return [result]

    with MockServer(EchoResource) as server:

        @attr.define
        class ItemPage(WebPage):
            browser_response: BrowserResponse
            http: HttpClient

            async def to_item(self):
                additional_response = await self.http.request(
                    server.root_url,
                    body=b"a",
                )
                return {
                    "main": str(self.browser_response.html),
                    "additional": additional_response.body.decode(),
                }

        class TestSpider(Spider):
            name = "test_spider"

            custom_settings = {
                "DOWNLOADER_MIDDLEWARES": {
                    "scrapy_poet.InjectionMiddleware": 543,
                },
                "SCRAPY_POET_PROVIDERS": {
                    BrowserResponseProvider: 1100,
                },
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            async def parse(self, response: DummyResponse, page: ItemPage):
                item = await page.to_item()
                items.append(item)

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert provider_calls == 1
    assert items == [{"main": "", "additional": "a"}]


@attr.define
class BasicPage(WebPage):
    def to_item(self):
        return {"key": "value"}


class BaseSpider(Spider):
    name = "test_spider"
    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_poet.InjectionMiddleware": 543,
        },
    }


# See: https://github.com/scrapinghub/scrapy-poet/issues/48
def _assert_warning_messages(
    record, index: Optional[List] = None, not_existing: bool = False
):
    index = index or [0, 1]

    expected_warnings = [
        # From injection.py:
        "A request has been encountered with callback=None which "
        "defaults to the parse() method. If the parse() method is "
        "annotated with scrapy_poet.DummyResponse (or its subclasses), "
        "we're assuming this isn't intended and would simply ignore "
        "this annotation.\n\n"
        "See the Pitfalls doc for more info.",
        # From InjectionMiddleware:
        "A request has been encountered with callback=None which "
        "defaults to the parse() method. On such cases, annotated "
        "dependencies in the parse() method won't be built by "
        "scrapy-poet. However, if the request has callback=parse, "
        "the annotated dependencies will be built.\n\n"
        "See the Pitfalls doc for more info.",
    ]

    expected_warning_found = [False] * len(index)

    for result_warning in record.list:
        for idx in index:
            if expected_warnings[idx] in str(result_warning.message):
                expected_warning_found[idx] = True

    if not not_existing:
        assert all(expected_warning_found)
    else:
        assert not any(expected_warning_found)


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_dummy_response() -> None:
    """If request.callback == None and the parse() method only has a single
    parameter of ``response: DummyResponse``, then a warning should be issued.

    This also means that even if the response is annotated with ``DummyResponse``,
    it's still downloaded as opposed to being skipped.
    """

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            start_urls = [server.root_url]

            def parse(self, response: DummyResponse):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record, index=[0])
    assert not isinstance(collected["response"], DummyResponse)


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_response() -> None:
    """Similar to ``test_parse_callback_none_dummy_response()`` but instead of
    ``response: DummyResponse``, it's ``response: scrapy.http.Response``.

    No warnings should be issued here.
    """

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            start_urls = [server.root_url]

            def parse(self, response: scrapy.http.Response):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record, not_existing=True)
    assert not isinstance(collected["response"], DummyResponse)


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_no_annotated_deps() -> None:
    """Similar to ``test_parse_callback_none_dummy_response()`` but there are no
    annotated dependencies.

    No warnings should be issued here.
    """

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(Spider):
            start_urls = [server.root_url]

            def parse(self, response):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with warnings.catch_warnings(record=True) as warning_msg:
            yield crawler.crawl()

    assert not warning_msg
    assert isinstance(collected["response"], scrapy.http.Response)


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_with_deps(caplog) -> None:
    """Same with the ``test_parse_callback_none_dummy_response`` test but it
    confirms that the other dependencies requested by the parse() method isn't
    injected.

    Moreover, it results in a TypeError in Scrapy due to the missing argument.
    """

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            start_urls = [server.root_url]

            def parse(self, response: DummyResponse, page: BasicPage):
                pass

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record)

    if sys.version_info < (3, 10):
        expected_msg = (
            "TypeError: parse() missing 1 required positional argument: 'page'"
        )
    else:
        expected_msg = (
            "TypeError: test_parse_callback_none_with_deps.<locals>.TestSpider"
            ".parse() missing 1 required positional argument: 'page'"
        )
    assert expected_msg in caplog.text


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_with_deps_cb_kwargs(caplog) -> None:
    """Same with the ``test_parse_callback_none_with_deps`` but the dep is passed
    via the ``cb_kwargs`` Request parameter.

    No warnings should be issued here.
    """

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            def start_requests(self):
                page = BasicPage(web_poet.HttpResponse("https://example.com", b""))
                yield Request(server.root_url, cb_kwargs={"page": page})

            def parse(self, response: DummyResponse, page: BasicPage):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record, index=[0])
    assert not caplog.text  # no TypeError caused by missing ``page`` arg.
    assert not isinstance(collected["response"], DummyResponse)


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
@inlineCallbacks
def test_parse_callback_none_with_deps_cb_kwargs_incomplete(caplog) -> None:
    """Same with the ``test_parse_callback_none_with_deps_cb_kwargs`` but not
    all of the callback dependencies are available in the ``cb_kwargs`` Request
    parameter.
    """

    with MockServer(EchoResource) as server:

        @attr.define
        class AnotherPage(WebPage):
            pass

        class TestSpider(BaseSpider):
            def start_requests(self):
                page = BasicPage(web_poet.HttpResponse("https://example.com", b""))
                yield Request(server.root_url, cb_kwargs={"page": page})

            def parse(
                self,
                response: DummyResponse,
                page: BasicPage,
                page2: AnotherPage,
            ):
                pass

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record)

    if sys.version_info < (3, 10):
        expected_msg = (
            "TypeError: parse() missing 1 required positional argument: 'page2'"
        )
    else:
        expected_msg = (
            "TypeError: test_parse_callback_none_with_deps_cb_kwargs_incomplete."
            "<locals>.TestSpider.parse() missing 1 required positional argument: 'page2'"
        )
    assert expected_msg in caplog.text


@pytest.mark.skipif(
    not is_min_scrapy_version("2.8.0"),
    reason="NO_CALLBACK not available in Scrapy < 2.8",
)
@inlineCallbacks
def test_parse_callback_NO_CALLBACK(caplog) -> None:
    """See: https://github.com/scrapinghub/scrapy-poet/issues/118"""

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            start_urls = [server.root_url]

            def parse(self, response: DummyResponse):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record, not_existing=True)
    assert not caplog.text
    assert isinstance(collected["response"], DummyResponse)


@pytest.mark.skipif(
    not is_min_scrapy_version("2.8.0"),
    reason="NO_CALLBACK not available in Scrapy < 2.8",
)
@inlineCallbacks
def test_parse_callback_NO_CALLBACK_with_page_dep(caplog) -> None:
    """See: https://github.com/scrapinghub/scrapy-poet/issues/118

    Similar to ``test_parse_callback_NO_CALLBACK()`` but with a page object
    dependency in ``parse()`` callback.
    """

    collected = {}

    with MockServer(EchoResource) as server:

        class TestSpider(BaseSpider):
            start_urls = [server.root_url]

            def parse(self, response: DummyResponse, page: BasicPage):
                collected["response"] = response

        crawler = make_crawler(TestSpider, {})

        with pytest.warns(UserWarning) as record:
            yield crawler.crawl()

    _assert_warning_messages(record, not_existing=True)
    assert not caplog.text
    assert not isinstance(collected["response"], DummyResponse)
