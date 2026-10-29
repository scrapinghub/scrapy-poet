"""Integration tests for InjectionMiddleware.get_page() and get_item()."""

from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import pytest
import scrapy
from scrapy import Request
from scrapy.utils.defer import deferred_f_from_coro_f
from web_poet import (
    ApplyRule,
    HttpRequest,
    HttpResponse,
    ItemPage,
    PageParams,
    RequestUrl,
    WebPage,
)

from scrapy_poet import InjectionMiddleware, callback_for
from scrapy_poet.utils import is_min_scrapy_version
from scrapy_poet.utils.testing import ProductHtml, crawl_items_async

pytestmark = pytest.mark.skipif(
    not is_min_scrapy_version("2.14"),
    reason="Requires Scrapy 2.14+",
)

# ---------------------------------------------------------------------------
# Page / item fixtures
# ---------------------------------------------------------------------------


class ProductPage(WebPage[Any]):
    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return {
            "name": self.css(".name::text").get(),
            "price": self.css(".price::text").get(),
        }


class ProductItem(dict[str, Any]):
    pass


class AsyncProductPage(ItemPage[ProductItem]):
    """Page object whose to_item() is async, to exercise the await branch."""

    def __init__(self, url: RequestUrl) -> None:
        self._url = url

    async def to_item(self) -> ProductItem:
        return ProductItem(url=str(self._url))


# ---------------------------------------------------------------------------
# Spider helpers
# ---------------------------------------------------------------------------


def _make_spider(
    start_coro: Callable[[Any], AsyncIterator[Any]],
) -> type[scrapy.Spider]:
    """Wrap a coroutine factory as a spider's start() method."""

    class _Spider(scrapy.Spider):
        name = "test"
        url: str

        async def start(self) -> AsyncIterator[Any]:
            async for item in start_coro(self):
                yield item

    return _Spider


# ---------------------------------------------------------------------------
# get_page() tests
# ---------------------------------------------------------------------------


@deferred_f_from_coro_f
async def test_get_page_with_url_string(settings: dict[str, Any]) -> None:
    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(spider.url, ProductPage)
        yield page.to_item()

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_page_with_scrapy_request(settings: dict[str, Any]) -> None:
    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(Request(spider.url), ProductPage)
        yield page.to_item()

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_page_with_http_request(settings: dict[str, Any]) -> None:
    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(HttpRequest(url=spider.url), ProductPage)
        yield page.to_item()

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_page_with_request_url(settings: dict[str, Any]) -> None:
    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(RequestUrl(spider.url), ProductPage)
        yield page.to_item()

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_page_with_page_params(settings: dict[str, Any]) -> None:
    class ParamsPage(ItemPage[dict[str, Any]]):
        def __init__(self, params: PageParams) -> None:  # type: ignore[type-arg]
            self._params = params

        def to_item(self) -> dict[str, Any]:  # type: ignore[override]
            return dict(self._params)

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(spider.url, ParamsPage, page_params={"key": "val"})
        yield page.to_item()

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"key": "val"}]


# ---------------------------------------------------------------------------
# get_item() tests
# ---------------------------------------------------------------------------


@deferred_f_from_coro_f
async def test_get_item_with_page_class(settings: dict[str, Any]) -> None:
    """Passing a page class to get_item() calls to_item() automatically."""

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        yield await mw.get_item(spider.url, ProductPage)

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_item_with_item_class(settings: dict[str, Any]) -> None:
    """Passing an item class resolves the page class via the registry."""
    settings["SCRAPY_POET_RULES"] = [
        ApplyRule("", use=ProductPage, to_return=ProductItem)
    ]

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        yield await mw.get_item(spider.url, ProductItem)

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_item_with_async_to_item(settings: dict[str, Any]) -> None:
    """get_item() awaits to_item() when it returns a coroutine."""

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        yield await mw.get_item(spider.url, AsyncProductPage)

    Spider = _make_spider(run)
    items, url, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [ProductItem(url=url)]


@deferred_f_from_coro_f
async def test_get_item_unregistered_item_class_raises(
    settings: dict[str, Any],
) -> None:
    class UnknownItem(dict[str, Any]):
        pass

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        try:
            yield await mw.get_item(spider.url, UnknownItem)
        except ValueError as exc:
            yield {"error": str(exc)}

    Spider = _make_spider(run)
    items, _, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert len(items) == 1
    assert "No page class is registered" in items[0]["error"]


@deferred_f_from_coro_f
async def test_regular_callback_injection_unaffected(settings: dict[str, Any]) -> None:
    """Normal callback-based injection still works after adding get_page/get_item."""

    class GetPageSpider(scrapy.Spider):
        name = "test"
        url: str

        def start_requests(self) -> Iterator[Request]:
            yield Request(self.url, callback=callback_for(ProductPage))

        async def start(self) -> AsyncIterator[Any]:
            for item_or_request in self.start_requests():
                yield item_or_request

    items, _, _ = await crawl_items_async(GetPageSpider, ProductHtml, settings)
    assert items == [{"name": "Chocolate", "price": "22€"}]


@deferred_f_from_coro_f
async def test_get_page_with_provided_class(settings: dict[str, Any]) -> None:
    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        response = await mw.get_page(spider.url, HttpResponse)
        yield {"url": str(response.url)}

    Spider = _make_spider(run)
    items, url, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"url": url}]


@deferred_f_from_coro_f
async def test_get_page_with_override(settings: dict[str, Any]) -> None:
    class OverridingPage(ItemPage[dict[str, Any]]):
        def __init__(self, url: RequestUrl) -> None:
            self._url = url

        def to_item(self) -> dict[str, Any]:  # type: ignore[override]
            return {"url": str(self._url)}

    settings["SCRAPY_POET_RULES"] = [
        ApplyRule("", use=OverridingPage, instead_of=ProductPage)
    ]

    async def run(spider: Any) -> AsyncIterator[Any]:
        mw = spider.crawler.get_downloader_middleware(InjectionMiddleware)
        page = await mw.get_page(spider.url, ProductPage)
        yield page.to_item()

    Spider = _make_spider(run)
    items, url, _ = await crawl_items_async(Spider, ProductHtml, settings)
    assert items == [{"url": url}]
