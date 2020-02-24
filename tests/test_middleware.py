# -*- coding: utf-8 -*-
import scrapy
from scrapy import Request
from pytest_twisted import inlineCallbacks

import attr

from scrapy_po import WebPage, callback_for, ItemWebPage
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
class Breadcrumbs(WebPage):
    def get(self):
        return {a.css('::text').get(): a.attrib['href']
                for a in self.css(".breadcrumbs a")}


@attr.s(auto_attribs=True)
class Product(ItemWebPage):
    breadcrumbs: Breadcrumbs

    def to_item(self):
        return {
            'name': self.css(".name::text").get(),
            'price': self.css(".price::text").get(),
            'description': self.css(".description").get(),
            'category': " / ".join(self.breadcrumbs.get().keys())
        }


class SingleUrlSpider(scrapy.Spider):
    url = None

    def start_requests(self):
        yield Request(self.url, capture_exceptions(callback_for(Product)))


@inlineCallbacks
def test_test(settings):
    items, url, crawler = yield crawl_items(SingleUrlSpider, ProductHtml,
                                            settings)
    assert len(items) == 1
    resp = items[0]
    if 'exception' in resp:
        raise resp['exception']
    assert resp == {
        'name': 'Chocolate',
        'price': '22€',
        'description': '<p class="description">The best chocolate ever</p>',
        'category': 'Food / Sweets'}
