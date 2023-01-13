import socket
from typing import Optional, Type, Union
from unittest import mock

import attr
import pytest
import scrapy
from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from scrapy.http import Response
from scrapy.utils.log import configure_logging
from scrapy.utils.test import get_crawler
from twisted.internet.threads import deferToThread
from url_matcher.util import get_domain
from web_poet import default_registry
from web_poet.page_inputs import HttpResponse, RequestUrl, ResponseUrl
from web_poet.pages import ItemPage, WebPage

from scrapy_poet import DummyResponse, InjectionMiddleware, callback_for
from scrapy_poet.cache import SqlitedictCache
from scrapy_poet.page_input_providers import PageObjectInputProvider
from tests.mockserver import get_ephemeral_port
from tests.utils import HtmlResource, capture_exceptions, crawl_items, crawl_single_item


class ProductHtml(HtmlResource):
    html = """
    <html>
        <div class="breadcrumbs">
            <a href="/food">Food</a> /
            <a href="/food/sweets">Sweets</a>
        </div>
        <h1 class="name">Chocolate</h1>
        <p>Price: <span class="price">22€</span></p>
        <p class="description">The best chocolate ever</p>
    </html>
    """


def spider_for(injectable: Type):
    class InjectableSpider(scrapy.Spider):

        url = None
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": {
                WithFuturesProvider: 1,
                WithDeferredProvider: 2,
                ExtraClassDataProvider: 3,
            }
        }

        def start_requests(self):
            yield Request(self.url, capture_exceptions(callback_for(injectable)))

    return InjectableSpider


@attr.s(auto_attribs=True)
class BreadcrumbsExtraction(WebPage):
    def get(self):
        return {
            a.css("::text").get(): a.attrib["href"] for a in self.css(".breadcrumbs a")
        }


@attr.s(auto_attribs=True)
class ProductPage(WebPage):
    breadcrumbs: BreadcrumbsExtraction

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css(".name::text").get(),
            "price": self.xpath('//*[@class="price"]/text()').get(),
            "description": self.css(".description::text").get(),
            "category": " / ".join(self.breadcrumbs.get().keys()),
        }


@attr.s(auto_attribs=True)
class OverridenBreadcrumbsExtraction(WebPage):
    def get(self):
        return {"overriden_breadcrumb": "http://example.com"}


@inlineCallbacks
def test_basic_case(settings):
    item, url, _ = yield crawl_single_item(
        spider_for(ProductPage), ProductHtml, settings
    )
    assert item == {
        "url": url,
        "name": "Chocolate",
        "price": "22€",
        "description": "The best chocolate ever",
        "category": "Food / Sweets",
    }


@inlineCallbacks
def test_overrides(settings):
    host = socket.gethostbyname(socket.gethostname())
    domain = get_domain(host)
    port = get_ephemeral_port()
    settings["SCRAPY_POET_OVERRIDES"] = [
        (f"{domain}:{port}", OverridenBreadcrumbsExtraction, BreadcrumbsExtraction)
    ]
    item, url, _ = yield crawl_single_item(
        spider_for(ProductPage), ProductHtml, settings, port=port
    )
    assert item == {
        "url": url,
        "name": "Chocolate",
        "price": "22€",
        "description": "The best chocolate ever",
        "category": "overriden_breadcrumb",
    }


@attr.s(auto_attribs=True)
class OptionalAndUnionPage(WebPage):
    breadcrumbs: BreadcrumbsExtraction
    opt_check_1: Optional[BreadcrumbsExtraction]
    opt_check_2: Optional[str]  # str is not Injectable, so None expected here
    union_check_1: Union[BreadcrumbsExtraction, HttpResponse]  # Breadcrumbs is injected
    union_check_2: Union[str, HttpResponse]  # HttpResponse is injected
    union_check_3: Union[Optional[str], HttpResponse]  # None is injected
    union_check_4: Union[None, str, HttpResponse]  # None is injected
    union_check_5: Union[BreadcrumbsExtraction, None, str]  # Breadcrumbs is injected

    def to_item(self):
        return attr.asdict(self, recurse=False)


@inlineCallbacks
def test_optional_and_unions(settings):
    item, _, _ = yield crawl_single_item(
        spider_for(OptionalAndUnionPage), ProductHtml, settings
    )
    assert item["breadcrumbs"].response is item["response"]
    assert item["opt_check_1"] is item["breadcrumbs"]
    assert item["opt_check_2"] is None
    assert item["union_check_1"] is item["breadcrumbs"]
    assert item["union_check_2"] is item["breadcrumbs"].response
    assert item["union_check_3"] is None
    assert item["union_check_5"] is item["breadcrumbs"]


@attr.s(auto_attribs=True)
class ProvidedWithDeferred:
    msg: str
    response: Optional[HttpResponse]  # it should be None because this class is provided


@attr.s(auto_attribs=True)
class ProvidedWithFutures(ProvidedWithDeferred):
    pass


class WithDeferredProvider(PageObjectInputProvider):

    provided_classes = {ProvidedWithDeferred}

    @inlineCallbacks
    def __call__(self, to_provide, response: scrapy.http.Response):
        five = yield deferToThread(lambda: 5)
        return [ProvidedWithDeferred(f"Provided {five}!", None)]


class WithFuturesProvider(PageObjectInputProvider):

    provided_classes = {ProvidedWithFutures}

    async def async_fn(self):
        return 5

    async def __call__(self, to_provide):
        five = await self.async_fn()
        return [ProvidedWithFutures(f"Provided {five}!", None)]


@attr.s(auto_attribs=True)
class ExtraClassData(ItemPage):
    msg: str

    def to_item(self):
        return {"msg": self.msg}


class ExtraClassDataProvider(PageObjectInputProvider):

    provided_classes = {ExtraClassData}

    def __call__(self, to_provide):
        # This should generate a runtime error in Injection Middleware because
        # we're returning a class that's not listed in self.provided_classes
        return {
            ExtraClassData: ExtraClassData("this should be returned"),
            HttpResponse: HttpResponse("example.com", b"this shouldn't"),
        }


@attr.s(auto_attribs=True)
class ProvidedWithDeferredPage(WebPage):
    provided: ProvidedWithDeferred

    def to_item(self):
        return attr.asdict(self, recurse=False)


@attr.s(auto_attribs=True)
class ProvidedWithFuturesPage(ProvidedWithDeferredPage):
    provided: ProvidedWithFutures


@pytest.mark.parametrize("type_", [ProvidedWithDeferredPage, ProvidedWithFuturesPage])
@inlineCallbacks
def test_providers(settings, type_):
    item, _, _ = yield crawl_single_item(spider_for(type_), ProductHtml, settings)
    assert item["provided"].msg == "Provided 5!"
    assert item["provided"].response is None


@inlineCallbacks
def test_providers_returning_wrong_classes(settings):
    """Injection Middleware should raise a runtime error whenever a provider
    returns instances of classes that they're not supposed to provide.
    """
    with pytest.raises(AssertionError):
        yield crawl_single_item(spider_for(ExtraClassData), ProductHtml, settings)


class MultiArgsCallbackSpider(scrapy.Spider):

    url = None
    custom_settings = {"SCRAPY_POET_PROVIDERS": {WithDeferredProvider: 1}}

    def start_requests(self):
        yield Request(
            self.url, self.parse, cb_kwargs={"cb_arg": "arg!", "cb_arg2": False}
        )

    def parse(
        self,
        response,
        product: ProductPage,
        provided: ProvidedWithDeferred,
        cb_arg: Optional[str],
        cb_arg2: Optional[bool],
        non_cb_arg: Optional[str],
    ):
        yield {
            "product": product,
            "provided": provided,
            "cb_arg": cb_arg,
            "cb_arg2": cb_arg2,
            "non_cb_arg": non_cb_arg,
        }


@inlineCallbacks
def test_multi_args_callbacks(settings):
    item, _, _ = yield crawl_single_item(MultiArgsCallbackSpider, ProductHtml, settings)
    assert type(item["product"]) == ProductPage
    assert type(item["provided"]) == ProvidedWithDeferred
    assert item["cb_arg"] == "arg!"
    assert item["cb_arg2"] is False
    assert item["non_cb_arg"] is None


@attr.s(auto_attribs=True)
class UnressolvableProductPage(ProductPage):
    this_is_unresolvable: str


@inlineCallbacks
def test_injection_failure(settings):
    configure_logging(settings)
    items, url, crawler = yield crawl_items(
        spider_for(UnressolvableProductPage), ProductHtml, settings
    )
    assert items == []


class MySpider(scrapy.Spider):

    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response):
        return {
            "response": response,
        }


class SkipDownloadSpider(scrapy.Spider):

    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse):
        return {
            "response": response,
        }


@inlineCallbacks
def test_skip_downloads(settings):
    item, url, crawler = yield crawl_single_item(MySpider, ProductHtml, settings)
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is False
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1

    item, url, crawler = yield crawl_single_item(
        SkipDownloadSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is True
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1


class RequestUrlSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse, url: RequestUrl):
        return {
            "response": response,
            "url": url,
        }


@inlineCallbacks
def test_skip_download_request_url(settings):
    item, url, crawler = yield crawl_single_item(
        RequestUrlSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is True
    assert isinstance(item["url"], RequestUrl)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1


class ResponseUrlSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse, url: ResponseUrl):
        return {
            "response": response,
            "url": url,
        }


@inlineCallbacks
def test_skip_download_response_url(settings):
    item, url, crawler = yield crawl_single_item(
        ResponseUrlSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    # Even if the spider marked the response with DummyResponse, the response
    # is still needed since ResponseUrl depends on it.
    assert isinstance(item["response"], DummyResponse) is False
    assert isinstance(item["url"], ResponseUrl)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1


@attr.s(auto_attribs=True)
class ResponseUrlPage(WebPage):
    response_url: ResponseUrl

    def to_item(self):
        return {"response_url": self.response_url}


class ResponseUrlPageSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse, page: ResponseUrlPage):
        return page.to_item()


@inlineCallbacks
def test_skip_download_response_url_page(settings):
    item, url, crawler = yield crawl_single_item(
        ResponseUrlPageSpider, ProductHtml, settings
    )
    assert tuple(item.keys()) == ("response_url",)
    assert str(item["response_url"]) == url
    # Even if the spider marked the response with DummyResponse, the response
    # is still needed since ResponseUrl depends on it.
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0


@attr.s(auto_attribs=True)
class RequestUrlPage(ItemPage):
    url: RequestUrl

    def to_item(self):
        return {"url": self.url}


class RequestUrlPageSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse, page: RequestUrlPage):
        return page.to_item()


@inlineCallbacks
def test_skip_download_request_url_page(settings):
    item, url, crawler = yield crawl_single_item(
        RequestUrlPageSpider, ProductHtml, settings
    )
    assert tuple(item.keys()) == ("url",)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1


@mock.patch("scrapy_poet.injection.SqlitedictCache", spec=SqlitedictCache)
def test_cache_closed_on_spider_close(mock_sqlitedictcache, settings):
    def get_middleware(settings):
        crawler = get_crawler(Spider, settings)
        crawler.spider = crawler._create_spider("example.com")
        return InjectionMiddleware(crawler)

    mock_sqlitedictcache.return_value = mock.Mock()

    # no cache
    no_cache_middleware = get_middleware(settings)
    assert no_cache_middleware.injector.cache is None

    # cache is present
    settings.set("SCRAPY_POET_CACHE", "/tmp/cache")
    has_cache_middleware = get_middleware(settings)
    assert has_cache_middleware.injector.cache is not None

    spider = has_cache_middleware.crawler.spider
    has_cache_middleware.spider_closed(spider)
    assert mock_sqlitedictcache.mock_calls == [
        mock.call("/tmp/cache", compressed=True),
        mock.call().close(),
    ]


@inlineCallbacks
def test_web_poet_integration(settings):
    """This tests scrapy-poet's integration with web-poet most especially when
    populating override settings via:

        from web_poet import default_registry

        SCRAPY_POET_OVERRIDES = default_registry.get_rules()
    """

    # Only import them in this test scope since they need to be synced with
    # the URL of the Page Object annotated with @handle_urls.
    from tests.po_lib import PORT, POOverriden

    # Override rules are defined in `tests/po_lib/__init__.py`.
    rules = default_registry.get_rules()

    # Converting it to a set removes potential duplicate ApplyRules
    settings["SCRAPY_POET_OVERRIDES"] = set(rules)

    item, url, _ = yield crawl_single_item(
        spider_for(POOverriden), ProductHtml, settings, port=PORT
    )
    assert item == {"msg": "PO replacement"}
