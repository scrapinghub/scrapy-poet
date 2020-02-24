# -*- coding: utf-8 -*-
from scrapy.utils.log import configure_logging
from twisted.internet.task import deferLater
from typing import Optional, Union

import scrapy
from scrapy import Request
from pytest_twisted import inlineCallbacks

import attr

from scrapy_po import WebPage, callback_for, ItemWebPage
from scrapy_po.page_input_providers import provides, PageObjectInputProvider
from scrapy_po.page_inputs import ResponseData
from tests.utils import HtmlResource, crawl_items, capture_exceptions


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
class BreadcrumbsExtraction(WebPage):
    def get(self):
        return {a.css('::text').get(): a.attrib['href']
                for a in self.css(".breadcrumbs a")}


@attr.s(auto_attribs=True)
class ProductPage(ItemWebPage):
    breadcrumbs: BreadcrumbsExtraction

    def to_item(self):
        return {
            'name': self.css(".name::text").get(),
            'price': self.css(".price::text").get(),
            'description': self.css(".description::text").get(),
            'category': " / ".join(self.breadcrumbs.get().keys()),
        }


class ProductSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(self.url, capture_exceptions(callback_for(ProductPage)))


@inlineCallbacks
def test_basic_case(settings):
    items, url, crawler = yield crawl_items(ProductSpider, ProductHtml,
                                            settings)
    assert len(items) == 1
    resp = items[0]
    if 'exception' in resp:
        raise resp['exception']
    assert resp == {
        'name': 'Chocolate',
        'price': '22€',
        'description': 'The best chocolate ever',
        'category': 'Food / Sweets',
    }


@attr.s(auto_attribs=True)
class OptionalAndUnionPage(ItemWebPage):
    breadcrumbs: BreadcrumbsExtraction
    opt_check_1: Optional[BreadcrumbsExtraction]
    opt_check_2: Optional[str]  # str is not Injectable, so None expected here
    union_check_1: Union[BreadcrumbsExtraction, ResponseData]  # Breadcrumbs is injected
    union_check_2: Union[str, ResponseData]  # ResponseData is injected
    union_check_3: Union[Optional[str], ResponseData]  # None is injected
    union_check_4: Union[None, str, ResponseData]  # None is injected
    union_check_5: Union[BreadcrumbsExtraction, None, str]  # Breadcrumbs is injected

    def to_item(self):
        return attr.asdict(self, recurse=False)


class OptionalAndUnionSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(self.url, capture_exceptions(callback_for(OptionalAndUnionPage)))


@inlineCallbacks
def test_optional_and_unions(settings):
    items, url, crawler = yield crawl_items(OptionalAndUnionSpider, ProductHtml,
                                            settings)
    assert len(items) == 1
    resp = items[0]
    if 'exception' in resp:
        raise resp['exception']

    assert resp['breadcrumbs'].response is resp['response']
    assert resp['opt_check_1'] is resp['breadcrumbs']
    assert resp['opt_check_2'] is None
    assert resp['union_check_1'] is resp['breadcrumbs']
    assert resp['union_check_2'] is resp['breadcrumbs'].response
    assert resp['union_check_3'] is None
    assert resp['union_check_5'] is resp['breadcrumbs']


@attr.s(auto_attribs=True)
class ProvidedTestCls:
    msg: str
    response: ResponseData  # it should be always None


@provides(ProvidedTestCls)
class ResponseDataProvider(PageObjectInputProvider):
    def __call__(self):
        # TODO: test async
        return ProvidedTestCls("Provided!", None)


@attr.s(auto_attribs=True)
class ProvidersPage(ItemWebPage):
    provided: ProvidedTestCls

    def to_item(self):
        return attr.asdict(self, recurse=False)


class ProvidersSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(self.url, capture_exceptions(callback_for(ProvidersPage)))


@inlineCallbacks
def test_providers(settings):
    items, url, crawler = yield crawl_items(ProvidersSpider, ProductHtml,
                                            settings)
    assert len(items) == 1
    resp = items[0]
    if 'exception' in resp:
        raise resp['exception']

    assert resp['provided'].msg == "Provided!"
    assert resp['provided'].response == None


class MultiArgsCallbackSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(self.url, self.parse, cb_kwargs=dict(cb_arg="arg!"))

    def parse(self, response, product: ProductPage, provided: ProvidedTestCls,
             cb_arg: str):
        yield {
            'product': product,
            'provided': provided,
            'cb_arg': cb_arg
        }

@inlineCallbacks
def test_multi_args_callbacks(settings):
    items, url, crawler = yield crawl_items(MultiArgsCallbackSpider, ProductHtml,
                                            settings)
    assert len(items) == 1
    resp = items[0]

    assert type(resp['product']) == ProductPage
    assert type(resp['provided']) == ProvidedTestCls
    assert resp['cb_arg'] == "arg!"

