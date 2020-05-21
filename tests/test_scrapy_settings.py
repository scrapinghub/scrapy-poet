import attr
from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from scrapy.settings import Settings

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


@attr.s(auto_attribs=True)
class MySettings:

    robotstxt_obey: bool


@provides(MySettings)
class MySettingsProvider(PageObjectInputProvider):

    def __init__(self, settings: Settings):
        self.settings = settings

    def __call__(self):
        return MySettings(self.settings.getbool("ROBOTSTXT_OBEY"))


class MySpider(Spider):

    name = "my_spider"
    url = None

    def start_requests(self):
        yield Request(url=self.url, callback=self.parse)

    def parse(self, response, my_settings: MySettings):
        return {
            "name": response.css(".name::text").get(),
            "robotstxt_obey": my_settings.robotstxt_obey,
        }


@inlineCallbacks
def test_providers_can_access_scrapy_settings(settings):
    my_settings = settings.copy()
    my_settings["ROBOTSTXT_OBEY"] = True
    item, url, crawler = yield crawl_single_item(
        MySpider, ProductHtml, my_settings)
    assert item == {
        "name": "Chocolate",
        "robotstxt_obey": True,
    }

    my_settings = settings.copy()
    my_settings["ROBOTSTXT_OBEY"] = False
    item, url, crawler = yield crawl_single_item(
        MySpider, ProductHtml, my_settings)
    assert item == {
        "name": "Chocolate",
        "robotstxt_obey": False,
    }
