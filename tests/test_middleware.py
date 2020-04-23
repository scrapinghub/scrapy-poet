import attr

from typing import Optional, Union, Type

import scrapy

from pytest_twisted import inlineCallbacks
from core_po.objects import PageObject, WebPageObject
from core_po.responses import HTMLResponse
from scrapy import Request
from scrapy.http import Response
from scrapy.utils.log import configure_logging
from twisted.internet.defer import returnValue
from twisted.internet.threads import deferToThread

from scrapy_po import callback_for
from scrapy_po.providers import provides, InjectableProvider
from scrapy_po.utils import DummyResponse

from tests.utils import (
    HtmlResource,
    crawl_items,
    capture_exceptions,
    crawl_single_item,
)


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

        def start_requests(self):
            yield Request(self.url,
                          capture_exceptions(callback_for(injectable)))

    return InjectableSpider


@attr.s(auto_attribs=True)
class BreadcrumbsExtraction(WebPageObject):

    def serialize(self):
        return {a.css('::text').get(): a.attrib['href']
                for a in self.css(".breadcrumbs a")}


@attr.s(auto_attribs=True)
class ProductPage(WebPageObject):
    breadcrumbs: BreadcrumbsExtraction

    def serialize(self):
        return {
            'url': self.url,
            'name': self.css(".name::text").get(),
            'price': self.xpath('//*[@class="price"]/text()').get(),
            'description': self.css(".description::text").get(),
            'category': " / ".join(self.breadcrumbs.serialize().keys()),
        }


@inlineCallbacks
def test_basic_case(settings):
    item, url, _ = yield crawl_single_item(spider_for(ProductPage),
                                           ProductHtml, settings)
    assert item == {
        'url': url,
        'name': 'Chocolate',
        'price': '22€',
        'description': 'The best chocolate ever',
        'category': 'Food / Sweets',
    }


@attr.s(auto_attribs=True)
class OptionalAndUnionPage(WebPageObject):
    breadcrumbs: BreadcrumbsExtraction
    opt_check_1: Optional[BreadcrumbsExtraction]
    opt_check_2: Optional[str]  # str is not Injectable, so None expected here
    union_check_1: Union[BreadcrumbsExtraction, HTMLResponse]  # Breadcrumbs is injected
    union_check_2: Union[str, HTMLResponse]  # HTMLResponse is injected
    union_check_3: Union[Optional[str], HTMLResponse]  # None is injected
    union_check_4: Union[None, str, HTMLResponse]  # None is injected
    union_check_5: Union[BreadcrumbsExtraction, None, str]  # Breadcrumbs is injected

    def serialize(self):
        return attr.asdict(self, recurse=False)


@inlineCallbacks
def test_optional_and_unions(settings):
    item, _, _ = yield crawl_single_item(spider_for(OptionalAndUnionPage),
                                         ProductHtml, settings)
    assert item['breadcrumbs'].html_response is item['html_response']
    assert item['opt_check_1'] is item['breadcrumbs']
    assert item['opt_check_2'] is None
    assert item['union_check_1'] is item['breadcrumbs']
    assert item['union_check_2'] is item['breadcrumbs'].html_response
    assert item['union_check_3'] is None
    assert item['union_check_5'] is item['breadcrumbs']


@attr.s(auto_attribs=True)
class ProvidedAsyncTest:

    msg: str
    html_response: HTMLResponse  # it should be None because this class is provided


@provides(ProvidedAsyncTest)
class AsyncHTMLResponseProvider(InjectableProvider):

    def __init__(self, response: scrapy.http.Response):
        self.response = response

    @inlineCallbacks
    def __call__(self):
        five = yield deferToThread(lambda: 5)
        raise returnValue(ProvidedAsyncTest(f"Provided {five}!", None))


@attr.s(auto_attribs=True)
class ProvidersPage(WebPageObject):

    provided: ProvidedAsyncTest

    def serialize(self):
        return attr.asdict(self, recurse=False)


@inlineCallbacks
def test_providers(settings):
    item, _, _ = yield crawl_single_item(spider_for(ProvidersPage),
                                         ProductHtml, settings)
    assert item['provided'].msg == "Provided 5!"
    assert item['provided'].html_response is None


class MultiArgsCallbackSpider(scrapy.Spider):

    url = None

    def start_requests(self):
        yield Request(self.url, self.parse, cb_kwargs=dict(cb_arg="arg!"))

    def parse(self, response, product: ProductPage, provided: ProvidedAsyncTest,
              cb_arg: Optional[str], non_cb_arg: Optional[str]):
        yield {
            'product': product,
            'provided': provided,
            'cb_arg': cb_arg,
            'non_cb_arg': non_cb_arg,
        }


@inlineCallbacks
def test_multi_args_callbacks(settings):
    item, _, _ = yield crawl_single_item(MultiArgsCallbackSpider, ProductHtml,
                                         settings)
    assert type(item['product']) == ProductPage
    assert type(item['provided']) == ProvidedAsyncTest
    assert item['cb_arg'] == "arg!"
    assert item['non_cb_arg'] is None


@attr.s(auto_attribs=True)
class UnressolvableProductPage(ProductPage):
    this_is_unresolvable: str


@inlineCallbacks
def test_injection_failure(settings):
    configure_logging(settings)
    items, url, crawler = yield crawl_items(
        spider_for(UnressolvableProductPage), ProductHtml, settings)
    assert items == []


class MySpider(scrapy.Spider):

    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response):
        return {
            'response': response,
        }


class SkipDownloadSpider(scrapy.Spider):

    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response: DummyResponse):
        return {
            'response': response,
        }


@inlineCallbacks
def test_skip_downloads(settings):
    item, url, crawler = yield crawl_single_item(
        MySpider, ProductHtml, settings)
    assert isinstance(item['response'], Response) is True
    assert isinstance(item['response'], DummyResponse) is False
    assert crawler.stats.get_stats().get('downloader/request_count', 0) == 1
    assert crawler.stats.get_stats().get('downloader/response_count', 0) == 1

    item, url, crawler = yield crawl_single_item(
        SkipDownloadSpider, ProductHtml, settings)
    assert isinstance(item['response'], Response) is True
    assert isinstance(item['response'], DummyResponse) is True
    assert crawler.stats.get_stats().get('downloader/request_count', 0) == 0
    assert crawler.stats.get_stats().get('downloader/response_count', 0) == 1
