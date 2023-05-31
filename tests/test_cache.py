from tempfile import TemporaryDirectory

from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from web_poet import WebPage, field

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource, make_crawler


@inlineCallbacks
def test_cache_no_errors(caplog) -> None:
    with TemporaryDirectory() as cache_dir:
        with MockServer(EchoResource) as server:

            class Page(WebPage):
                @field
                async def url(self):
                    return self.response.url

            class CacheSpider(Spider):
                name = "cache"

                custom_settings = {
                    "DOWNLOADER_MIDDLEWARES": {
                        "scrapy_poet.InjectionMiddleware": 543,
                    },
                    "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
                    "SCRAPY_POET_CACHE": cache_dir,
                }

                def start_requests(self):
                    yield Request(server.root_url, callback=self.parse_url)

                async def parse_url(self, response, page: Page):
                    await page.to_item()

            crawler = make_crawler(CacheSpider, {})
            yield crawler.crawl()

    assert all(record.levelname != "ERROR" for record in caplog.records)
