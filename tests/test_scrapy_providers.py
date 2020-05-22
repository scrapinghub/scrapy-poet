import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.crawler import Crawler
from scrapy.settings import Settings
from scrapy.statscollectors import StatsCollector

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


def make_spider(scrapy_class):

    class MySpider(Spider):

        name = "my_spider"
        url = None

        def start_requests(self):
            yield Request(url=self.url, callback=self.parse)

        def parse(self, response, obj: scrapy_class):
            return {"obj": obj}

    return MySpider


@inlineCallbacks
@pytest.mark.parametrize('scrapy_class', [
    Spider,
    Request,
    Response,
    Crawler,
    Settings,
    StatsCollector,
])
def test_scrapy_providers(scrapy_class, settings):
    item, url, crawler = yield crawl_single_item(
        make_spider(scrapy_class), ProductHtml, settings)
    assert isinstance(item["obj"], scrapy_class)
