import attr
import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Spider
from scrapy.http import Request
from web_poet.pages import ItemWebPage

from scrapy_poet.utils import _SCRAPY_PROVIDED_CLASSES
from scrapy_poet.repository import provides
from scrapy_poet.providers import PageObjectInputProvider

from tests.utils import crawl_items, crawl_single_item, HtmlResource


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


@inlineCallbacks
@pytest.mark.parametrize('scrapy_class', _SCRAPY_PROVIDED_CLASSES)
def test_scrapy_dependencies_on_providers(scrapy_class, settings):
    """Scrapy dependencies should be injected into Providers."""

    @attr.s(auto_attribs=True)
    class PageData:
        scrapy_class: str

    @provides(PageData)
    class PageDataProvider(PageObjectInputProvider):

        def __init__(self, obj: scrapy_class):
            self.obj = obj

        def __call__(self):
            return PageData(
                scrapy_class=scrapy_class.__name__,
            )

    @attr.s(auto_attribs=True)
    class Page(ItemWebPage):

        page_data: PageData

        def to_item(self):
            return {
                "scrapy_class": self.page_data.scrapy_class,
            }

    class MySpider(Spider):

        name = "my_spider"
        url = None

        def start_requests(self):
            yield Request(url=self.url, callback=self.parse)

        def parse(self, response, page: Page):
            return page.to_item()

    item, url, crawler = yield crawl_single_item(
        MySpider, ProductHtml, settings)
    assert item["scrapy_class"] == scrapy_class.__name__


@inlineCallbacks
@pytest.mark.parametrize('scrapy_class', _SCRAPY_PROVIDED_CLASSES)
def test_scrapy_dependencies_on_page_objects(scrapy_class, settings):
    """Scrapy dependencies should not be injected into Page Objects."""

    @attr.s(auto_attribs=True)
    class Page(ItemWebPage):

        scrapy_obj: scrapy_class

        def to_item(self):
            return {
                "scrapy_class": self.scrapy_obj.__class__.__name__,
            }

    class MySpider(Spider):

        name = "my_spider"
        url = None

        def start_requests(self):
            yield Request(url=self.url, callback=self.parse)

        def parse(self, response, page: Page):
            return page.to_item()

    items, url, crawler = yield crawl_items(
        MySpider, ProductHtml, settings)
    assert not items
