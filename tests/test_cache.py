from collections.abc import AsyncIterator, Iterator
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from scrapy import Request, Spider
from scrapy.http import Response
from scrapy.utils.defer import deferred_f_from_coro_f, maybe_deferred_to_future
from web_poet import ResponseUrl, WebPage, field

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource, _get_test_settings, make_crawler


@deferred_f_from_coro_f
async def test_cache_no_errors(caplog: pytest.LogCaptureFixture) -> None:
    with TemporaryDirectory() as cache_dir, MockServer(EchoResource) as server:

        class Page(WebPage[dict[str, Any]]):
            @field
            async def url(self) -> ResponseUrl:
                return self.response.url

        class CacheSpider(Spider):
            name = "cache"

            custom_settings = {
                **_get_test_settings(),
                "SCRAPY_POET_CACHE": cache_dir,
            }

            def start_requests(self) -> Iterator[Request]:
                yield Request(server.root_url, callback=self.parse_url)

            async def start(self) -> AsyncIterator[Any]:
                for item_or_request in self.start_requests():
                    yield item_or_request

            async def parse_url(self, response: Response, page: Page) -> None:
                await page.to_item()

        crawler = make_crawler(CacheSpider, {})
        await maybe_deferred_to_future(crawler.crawl())

    assert all(record.levelname != "ERROR" for record in caplog.records)
