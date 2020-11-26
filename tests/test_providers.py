from typing import Any, List

import attr
from pytest_twisted import inlineCallbacks
from twisted.python.failure import Failure

import scrapy
from scrapy import Request
from scrapy.crawler import Crawler
from scrapy.settings import Settings
from scrapy_poet.page_input_providers import PageObjectInputProvider
from tests.utils import crawl_single_item, HtmlResource


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

    provided_classes = {Price, Html}

    def __init__(self, crawler: Crawler):
        assert isinstance(crawler, Crawler)
        super().__init__(crawler)

    def __call__(self, to_provide, response: scrapy.http.Response, spider: scrapy.Spider):
        assert isinstance(spider, scrapy.Spider)
        ret: List[Any] = []
        if Price in to_provide:
            ret.append(Price(response.css(".price::text").get()))
        if Html in to_provide:
            ret.append(Html("Price Html!"))
        return ret


class NameHtmlDataProvider(PageObjectInputProvider):

    provided_classes = {Name, Html}.__contains__

    def __call__(self, to_provide, response: scrapy.http.Response, settings: Settings):
        assert isinstance(settings, Settings)
        ret: List[Any] = []
        if Name in to_provide:
            ret.append(Name(response.css(".name::text").get()))
        if Html in to_provide:
            ret.append(Html("Name Html!"))
        return ret


class PriceFirstMultiProviderSpider(scrapy.Spider):

    url = None
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            PriceHtmlDataProvider: 1,
            NameHtmlDataProvider: 2,
        }
    }

    def start_requests(self):
        yield Request(self.url, self.parse, errback=self.errback)

    def errback(self, failure: Failure):
        yield {"exception": failure.value}

    def parse(self, response, price: Price, name: Name, html: Html):
        yield {
            Price: price,
            Name: name,
            Html: html
        }


class NameFirstMultiProviderSpider(PriceFirstMultiProviderSpider):

    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            NameHtmlDataProvider: 1,
            PriceHtmlDataProvider: 2,
        }
    }


@inlineCallbacks
def test_name_first_spider(settings):
    item, _, _ = yield crawl_single_item(NameFirstMultiProviderSpider, ProductHtml,
                                         settings)
    assert item == {
        Price: Price("22€"),
        Name: Name("Chocolate"),
        Html: Html("Name Html!"),
    }


@inlineCallbacks
def test_price_first_spider(settings):
    item, _, _ = yield crawl_single_item(PriceFirstMultiProviderSpider, ProductHtml,
                                         settings)
    assert item == {
        Price: Price("22€"),
        Name: Name("Chocolate"),
        Html: Html("Price Html!"),
    }
