from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import attr
import pytest
from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.utils.defer import deferred_f_from_coro_f
from web_poet.pages import WebPage

from scrapy_poet.injection import SCRAPY_PROVIDED_CLASSES
from scrapy_poet.page_input_providers import (
    HttpResponseProvider,
    PageObjectInputProvider,
)
from scrapy_poet.utils.testing import (
    ProductHtml,
    crawl_items_async,
    crawl_single_item_async,
)


@pytest.mark.parametrize("scrapy_class", SCRAPY_PROVIDED_CLASSES)
@deferred_f_from_coro_f
async def test_scrapy_dependencies_on_providers(
    scrapy_class: type, settings: dict[str, Any]
) -> None:
    """Scrapy dependencies should be injected into Providers."""

    @attr.s(auto_attribs=True)
    class PageData:
        scrapy_class: str

    class PageDataProvider(PageObjectInputProvider):
        provided_classes = {PageData}

        def __call__(
            self,
            to_provide: set[Callable[..., Any]],
            obj: scrapy_class,  # type: ignore[valid-type]
        ) -> list[PageData]:
            return [PageData(scrapy_class=scrapy_class.__name__)]

    @attr.s(auto_attribs=True)
    class Page(WebPage[dict[str, Any]]):
        page_data: PageData

        def to_item(self) -> dict[str, Any]:  # type: ignore[override]
            return {
                "scrapy_class": self.page_data.scrapy_class,
            }

    class MySpider(Spider):
        name = "my_spider"
        url: str
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": {
                HttpResponseProvider: 1,
                PageDataProvider: 2,
            }
        }

        def start_requests(self) -> Iterator[Request]:
            yield Request(url=self.url, callback=self.parse)

        async def start(self) -> AsyncIterator[Any]:
            for item_or_request in self.start_requests():
                yield item_or_request

        def parse(self, response: Response, page: Page) -> dict[str, Any]:
            return page.to_item()

    item, *_ = await crawl_single_item_async(MySpider, ProductHtml, settings)
    assert item["scrapy_class"] == scrapy_class.__name__


@pytest.mark.parametrize("scrapy_class", SCRAPY_PROVIDED_CLASSES)
@deferred_f_from_coro_f
async def test_scrapy_dependencies_on_page_objects(
    scrapy_class: type, settings: dict[str, Any]
) -> None:
    """Scrapy dependencies should not be injected into Page Objects."""

    @attr.s(auto_attribs=True)
    class Page(WebPage[dict[str, Any]]):
        scrapy_obj: scrapy_class  # type: ignore[valid-type]

        def to_item(self) -> dict[str, Any]:  # type: ignore[override]
            return {
                "scrapy_class": self.scrapy_obj.__class__.__name__,  # type: ignore[attr-defined]
            }

    class MySpider(Spider):
        name = "my_spider"
        url: str

        def start_requests(self) -> Iterator[Request]:
            yield Request(url=self.url, callback=self.parse)

        async def start(self) -> AsyncIterator[Any]:
            for item_or_request in self.start_requests():
                yield item_or_request

        def parse(self, response: Response, page: Page) -> dict[str, Any]:
            return page.to_item()

    items, *_ = await crawl_items_async(MySpider, ProductHtml, settings)
    assert not items
