import attr
import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from scrapy.settings import Settings
from web_poet.pages import Injectable, ItemWebPage

from scrapy_poet.page_input_providers import (
    PageObjectInputProvider,
    provides,
)

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


@provides(Settings)
class SettingsProvider(PageObjectInputProvider):

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self):
        return self.settings


@attr.s(auto_attribs=True)
class ProductPage(ItemWebPage):

    settings: Settings

    @property
    def name(self):
        name = self.css(".name::text").get()
        if self.settings.getbool("UPPERCASE_NAME"):
            name = name.upper()

        return name

    def to_item(self):
        return {
            "name": self.name,
        }


class ProductSettings(Injectable):

    def __init__(self, settings: Settings):
        self.uppercase_name = settings.getbool("UPPERCASE_NAME")


@attr.s(auto_attribs=True)
class ProductPageWithDependency(ItemWebPage):

    settings: ProductSettings

    @property
    def name(self):
        name = self.css(".name::text").get()
        if self.settings.uppercase_name:
            name = name.upper()

        return name

    def to_item(self):
        return {
            "name": self.name,
        }


class ProductSpider(Spider):

    name = "product_spider"
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response, page: ProductPage):
        return page.to_item()


class ProductWithDependencySpider(Spider):

    name = "product_with_dependency_spider"
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response, page: ProductPageWithDependency):
        return page.to_item()


@inlineCallbacks
@pytest.mark.parametrize('spider_class,uppercase_name,expected_name', [
    (ProductSpider, True, "CHOCOLATE"),
    (ProductSpider, False, "Chocolate"),
    (ProductWithDependencySpider, True, "CHOCOLATE"),
    (ProductWithDependencySpider, False, "Chocolate"),
])
def test_settings(spider_class, uppercase_name, expected_name, settings):
    my_settings = settings.copy()
    my_settings["UPPERCASE_NAME"] = uppercase_name
    item, url, crawler = yield crawl_single_item(
        spider_class, ProductHtml, my_settings)
    assert item == {"name": expected_name}
