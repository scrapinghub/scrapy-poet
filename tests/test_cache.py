from tempfile import TemporaryDirectory

from scrapy import Request, Spider
from web_poet import WebPage, field

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource, _get_test_settings, make_crawler


async def test_cache_no_errors(caplog) -> None:
    with TemporaryDirectory() as cache_dir, MockServer(EchoResource) as server:

        class Page(WebPage):
            @field
            async def url(self):
                return self.response.url

        class CacheSpider(Spider):
            name = "cache"

            custom_settings = {
                **_get_test_settings(),
                "SCRAPY_POET_CACHE": cache_dir,
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse_url)

            async def start(self):
                for item_or_request in self.start_requests():
                    yield item_or_request

            async def parse_url(self, response, page: Page):
                await page.to_item()

        crawler = make_crawler(CacheSpider, {})
        await crawler.crawl()

    assert all(record.levelname != "ERROR" for record in caplog.records)
