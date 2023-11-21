from typing import Any, Callable, List, Set, Type
from unittest import mock

import attr
import scrapy
from pytest_twisted import ensureDeferred, inlineCallbacks
from scrapy import Request, Spider
from scrapy.settings import Settings
from scrapy.utils.test import get_crawler
from twisted.python.failure import Failure
from web_poet import (
    HttpClient,
    HttpRequest,
    HttpRequestBody,
    HttpRequestHeaders,
    HttpResponse,
    RequestUrl,
)
from web_poet.serialization import SerializedLeafData, register_serialization

from scrapy_poet import HttpResponseProvider
from scrapy_poet.injection import Injector
from scrapy_poet.page_input_providers import (
    HttpClientProvider,
    HttpRequestProvider,
    ItemProvider,
    PageObjectInputProvider,
    PageParamsProvider,
    StatsProvider,
)
from scrapy_poet.utils.mockserver import get_ephemeral_port
from scrapy_poet.utils.testing import (
    AsyncMock,
    HtmlResource,
    ProductHtml,
    crawl_single_item,
)


class NonProductHtml(HtmlResource):
    html = """
    <html>
        <p>This one is clearly not a product</p>
    </html>
    """


@attr.s(auto_attribs=True)
class Price:
    price: str


@attr.s(auto_attribs=True)
class Name:
    name: str


@attr.s(auto_attribs=True)
class Html:
    html: str


class PriceHtmlDataProvider(PageObjectInputProvider):
    name = "price_html"
    provided_classes = {Price, Html}

    def __init__(self, injector: Injector):
        assert isinstance(injector, Injector)
        super().__init__(injector)

    def __call__(
        self, to_provide, response: scrapy.http.Response, spider: scrapy.Spider
    ):
        assert isinstance(spider, scrapy.Spider)
        ret: List[Any] = []
        if Price in to_provide:
            ret.append(Price(response.css(".price::text").get()))
        if Html in to_provide:
            ret.append(Html("Price Html!"))
        return ret


class NameHtmlDataProvider(PageObjectInputProvider):
    name = "name_html"
    provided_classes = {Name, Html}.__contains__

    def __call__(self, to_provide, response: scrapy.http.Response, settings: Settings):
        assert isinstance(settings, Settings)
        ret: List[Any] = []
        if Name in to_provide:
            ret.append(Name(response.css(".name::text").get()))
        if Html in to_provide:
            ret.append(Html("Name Html!"))
        return ret


class HttpResponseProviderForTest(HttpResponseProvider):
    """Uses a fixed fingerprint because the test server is always changing the URL from test to test"""

    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        return "http://example.com"


for dep_cls in [Price, Name, Html]:
    # all these types have the same structure so we can DRY
    def _serialize(o: dep_cls) -> SerializedLeafData:  # type: ignore[valid-type]
        return {"txt": attr.astuple(o)[0].encode()}

    def _deserialize(cls: Type[dep_cls], data: SerializedLeafData) -> dep_cls:  # type: ignore[valid-type]
        return cls(data["txt"].decode())  # type: ignore[misc]

    register_serialization(_serialize, _deserialize)


class PriceFirstMultiProviderSpider(scrapy.Spider):
    url = None
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            HttpResponseProviderForTest: 0,
            PriceHtmlDataProvider: 1,
            NameHtmlDataProvider: 2,
        }
    }

    def start_requests(self):
        yield Request(self.url, self.parse, errback=self.errback)

    def errback(self, failure: Failure):
        yield {"exception": failure.value}

    def parse(
        self,
        response,
        price: Price,
        name: Name,
        html: Html,
        response_data: HttpResponse,
    ):
        yield {
            Price: price,
            Name: name,
            Html: html,
            "response_data_text": response_data.text,
        }


class NameFirstMultiProviderSpider(PriceFirstMultiProviderSpider):
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            HttpResponseProviderForTest: 0,
            NameHtmlDataProvider: 1,
            PriceHtmlDataProvider: 2,
        }
    }


@inlineCallbacks
def test_name_first_spider(settings, tmp_path):
    port = get_ephemeral_port()
    cache = tmp_path / "cache"
    settings.set("SCRAPY_POET_CACHE", str(cache))
    item, _, _ = yield crawl_single_item(
        NameFirstMultiProviderSpider, ProductHtml, settings, port=port
    )
    assert cache.exists()
    assert item == {
        Price: Price("22€"),
        Name: Name("Chocolate"),
        Html: Html("Name Html!"),
        "response_data_text": ProductHtml.html,
    }

    # Let's see that the cache is working. We use a different and wrong resource,
    # but it should be ignored by the cached version used
    item, _, _ = yield crawl_single_item(
        NameFirstMultiProviderSpider, NonProductHtml, settings, port=port
    )
    assert item == {
        Price: Price("22€"),
        Name: Name("Chocolate"),
        Html: Html("Name Html!"),
        "response_data_text": ProductHtml.html,
    }


@inlineCallbacks
def test_price_first_spider(settings):
    item, _, _ = yield crawl_single_item(
        PriceFirstMultiProviderSpider, ProductHtml, settings
    )
    assert item == {
        Price: Price("22€"),
        Name: Name("Chocolate"),
        Html: Html("Price Html!"),
        "response_data_text": ProductHtml.html,
    }


@ensureDeferred
async def test_http_client_provider(settings):
    crawler = get_crawler(Spider, settings)
    crawler.engine = AsyncMock()
    injector = Injector(crawler)

    with mock.patch(
        "scrapy_poet.page_input_providers.create_scrapy_downloader"
    ) as mock_factory:
        provider = HttpClientProvider(injector)
        results = provider(set(), crawler)
        assert isinstance(results[0], HttpClient)

    assert results[0]._request_downloader == mock_factory.return_value


@ensureDeferred
async def test_http_request_provider(settings):
    crawler = get_crawler(Spider, settings)
    injector = Injector(crawler)
    provider = HttpRequestProvider(injector)

    empty_scrapy_request = scrapy.http.Request("https://example.com")
    (empty_request,) = provider(set(), empty_scrapy_request)
    assert isinstance(empty_request, HttpRequest)
    assert isinstance(empty_request.url, RequestUrl)
    assert str(empty_request.url) == "https://example.com"
    assert empty_request.method == "GET"
    assert isinstance(empty_request.headers, HttpRequestHeaders)
    assert empty_request.headers == HttpRequestHeaders()
    assert isinstance(empty_request.body, HttpRequestBody)
    assert empty_request.body == HttpRequestBody()

    full_scrapy_request = scrapy.http.Request(
        "https://example.com", method="POST", body=b"a", headers={"a": "b"}
    )
    (full_request,) = provider(set(), full_scrapy_request)
    assert isinstance(full_request, HttpRequest)
    assert isinstance(full_request.url, RequestUrl)
    assert str(full_request.url) == "https://example.com"
    assert full_request.method == "POST"
    assert isinstance(full_request.headers, HttpRequestHeaders)
    assert full_request.headers == HttpRequestHeaders([("a", "b")])
    assert isinstance(full_request.body, HttpRequestBody)
    assert full_request.body == HttpRequestBody(b"a")


def test_page_params_provider(settings):
    crawler = get_crawler(Spider, settings)
    injector = Injector(crawler)
    provider = PageParamsProvider(injector)
    request = scrapy.http.Request("https://example.com")

    results = provider(set(), request)

    assert results[0] == {}

    expected_data = {"key": "value"}
    request.meta.update({"page_params": expected_data})
    results = provider(set(), request)

    assert results[0] == expected_data

    # Check that keys that are invalid Python variable names work.
    expected_data = {1: "a"}
    request.meta.update({"page_params": expected_data})
    results = provider(set(), request)

    assert results[0] == expected_data


def test_item_provider_cache(settings):
    """Note that the bulk of the tests for the ``ItemProvider`` alongside the
    ``Injector`` is tested in ``tests/test_web_poet_rules.py``.

    We'll only test its caching behavior here if its properly garbage collected.
    """

    crawler = get_crawler(Spider, settings)
    injector = Injector(crawler)
    provider = ItemProvider(injector)

    assert len(provider._cached_instances) == 0

    def inside():
        request = Request("https://example.com")
        provider.update_cache(request, {Name: Name("test")})
        assert len(provider._cached_instances) == 1

        cached_instance = provider.get_from_cache(request, Name)
        assert isinstance(cached_instance, Name)

    # The cache should be empty after the ``inside`` scope has finished which
    # means that the corresponding ``request`` and the contents under it are
    # garbage collected.
    inside()
    assert len(provider._cached_instances) == 0


def test_stats_provider(settings):
    crawler = get_crawler(Spider, settings)
    injector = Injector(crawler)
    provider = StatsProvider(injector)

    results = provider(set(), crawler)

    stats = results[0]
    assert stats._stats._stats == crawler.stats

    stats.set("a", "1")
    stats.set("b", 2)
    stats.inc("b")
    stats.inc("b", 5)
    stats.inc("c")

    expected = {"a": "1", "b": 8, "c": 1}
    expected = {f"poet/stats/{k}": v for k, v in expected.items()}
    actual = {k: v for k, v in crawler.stats._stats.items() if k in expected}
    assert actual == expected
