import json
from typing import Any, Callable, List, Sequence, Set
from unittest import mock

import attr
import scrapy
from pytest_twisted import ensureDeferred, inlineCallbacks
from scrapy import Request, Spider
from scrapy.settings import Settings
from scrapy.utils.test import get_crawler
from twisted.python.failure import Failure
from web_poet import HttpClient, HttpResponse

from scrapy_poet import HttpResponseProvider
from scrapy_poet.injection import Injector
from scrapy_poet.page_input_providers import (
    CacheDataProviderMixin,
    HttpClientProvider,
    ItemProvider,
    PageObjectInputProvider,
    PageParamsProvider,
)
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


class PriceHtmlDataProvider(PageObjectInputProvider, CacheDataProviderMixin):

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

    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        return "http://example.com"

    def serialize(self, result: Sequence[Any]) -> Any:
        return result

    def deserialize(self, data: Any) -> Sequence[Any]:
        return data


class NameHtmlDataProvider(PageObjectInputProvider, CacheDataProviderMixin):

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

    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        return "http://example.com"

    def serialize(self, result: Sequence[Any]) -> Any:
        return result

    def deserialize(self, data: Any) -> Sequence[Any]:
        return data


class HttpResponseProviderForTest(HttpResponseProvider):
    """Uses a fixed fingerprint because the test server is always changing the URL from test to test"""

    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        return "http://example.com"


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
    cache = tmp_path / "cache.sqlite3"
    settings.set("SCRAPY_POET_CACHE", str(cache))
    item, _, _ = yield crawl_single_item(
        NameFirstMultiProviderSpider, ProductHtml, settings
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
        NameFirstMultiProviderSpider, NonProductHtml, settings
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


def test_response_data_provider_fingerprint(settings):
    crawler = get_crawler(Spider, settings)
    injector = Injector(crawler)
    rdp = HttpResponseProvider(injector)
    request = scrapy.http.Request("https://example.com")

    # The fingerprint should be readable since it's JSON-encoded.
    fp = rdp.fingerprint(scrapy.http.Response, request)
    assert json.loads(fp)


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
