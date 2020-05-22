import attr
import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from scrapy.settings import Settings
from web_poet.pages import Injectable, ItemWebPage

from scrapy_poet.page_input_providers import provides, PageObjectInputProvider

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
class ProductSettings:

    uppercase_name: bool


@provides(ProductSettings)
class ProductSettingsProvider(PageObjectInputProvider):

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self):
        return ProductSettings(
            uppercase_name=self.settings.getbool("UPPERCASE_NAME"),
        )


@attr.s(auto_attribs=True)
class ProductPage(ItemWebPage):

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


@inlineCallbacks
@pytest.mark.parametrize('spider_class,uppercase_name,expected_name', [
    (ProductSpider, True, "CHOCOLATE"),
    (ProductSpider, False, "Chocolate"),
])
def test_settings(spider_class, uppercase_name, expected_name, settings):
    my_settings = settings.copy()
    my_settings["UPPERCASE_NAME"] = uppercase_name
    item, url, crawler = yield crawl_single_item(
        spider_class, ProductHtml, my_settings)
    assert item == {"name": expected_name}
