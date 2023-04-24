import attr
import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Spider
from scrapy.http import Request
from web_poet.pages import WebPage

from scrapy_poet.injection import SCRAPY_PROVIDED_CLASSES
from scrapy_poet.page_input_providers import (
    HttpResponseProvider,
    PageObjectInputProvider,
)
from scrapy_poet.utils.testing import ProductHtml, crawl_items, crawl_single_item


@inlineCallbacks
@pytest.mark.parametrize("scrapy_class", SCRAPY_PROVIDED_CLASSES)
def test_scrapy_dependencies_on_providers(scrapy_class, settings) -> None:
    """Scrapy dependencies should be injected into Providers."""

    @attr.s(auto_attribs=True)
    class PageData:
        scrapy_class: str

    class PageDataProvider(PageObjectInputProvider):

        provided_classes = {PageData}

        def __call__(self, to_provide, obj: scrapy_class):  # type: ignore[valid-type]
            return [PageData(scrapy_class=scrapy_class.__name__)]

    @attr.s(auto_attribs=True)
    class Page(WebPage):

        page_data: PageData

        def to_item(self):
            return {
                "scrapy_class": self.page_data.scrapy_class,
            }

    class MySpider(Spider):

        name = "my_spider"
        url = None
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": {
                HttpResponseProvider: 1,
                PageDataProvider: 2,
            }
        }

        def start_requests(self):
            yield Request(url=self.url, callback=self.parse)

        def parse(self, response, page: Page):
            return page.to_item()

    item, url, crawler = yield crawl_single_item(MySpider, ProductHtml, settings)
    assert item["scrapy_class"] == scrapy_class.__name__


@inlineCallbacks
@pytest.mark.parametrize("scrapy_class", SCRAPY_PROVIDED_CLASSES)
def test_scrapy_dependencies_on_page_objects(scrapy_class, settings) -> None:
    """Scrapy dependencies should not be injected into Page Objects."""

    @attr.s(auto_attribs=True)
    class Page(WebPage):

        scrapy_obj: scrapy_class  # type: ignore[valid-type]

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

    items, url, crawler = yield crawl_items(MySpider, ProductHtml, settings)
    assert not items
