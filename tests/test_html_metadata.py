from collections.abc import AsyncIterator
from typing import Any

import attrs
import frostwork
import pytest
import scrapy
from scrapy.http import TextResponse
from scrapy.utils.defer import deferred_f_from_coro_f
from web_poet import WebPage, css_get, field
from web_poet._frostwork import _extract as extract

from scrapy_poet import HtmlMetadataMiddleware
from scrapy_poet.utils.testing import HtmlResource, crawl_items_async

# Scrapy < 2.20
if not hasattr(TextResponse, "meta_refresh"):
    pytest.skip("Scrapy without TextResponse.meta_refresh", allow_module_level=True)

from scrapy.http.response.text import MetaRefresh


class MetadataHtml(HtmlResource):
    content_type = "text/html; charset=utf-8"
    html = """
    <html>
        <base href="/food/">
        <meta http-equiv="refresh" content="1000; url=next">
        <h1>Chocolate</h1>
    </html>
    """


class UndeclaredEncodingHtml(MetadataHtml):
    content_type = "text/html"


class NoRefreshHtml(MetadataHtml):
    html = """
    <html>
        <base href="/food/">
        <h1>Chocolate</h1>
    </html>
    """


@attrs.define
class NamePage(WebPage[Any]):
    name = field(css_get("h1::text"))


@attrs.define
class UndeclaredPage(WebPage[Any]):
    pass


class MetadataSpider(scrapy.Spider):
    name = "html_metadata"
    url: str

    async def start(self) -> AsyncIterator[Any]:
        yield scrapy.Request(self.url, callback=self.parse_page)

    async def parse_page(self, response: Any, page: NamePage) -> Any:
        yield {
            "name": page.name,
            "page_base_url": page.base_url,
            "base_url": response.base_url,
            "meta_refresh": response.meta_refresh,
        }


class ResponseSpider(MetadataSpider):
    async def parse_page(self, response: Any) -> Any:  # type: ignore[override]
        yield {
            "base_url": response.base_url,
            "meta_refresh": response.meta_refresh,
        }


class UndeclaredSpider(MetadataSpider):
    async def parse_page(self, response: Any, page: UndeclaredPage) -> Any:  # type: ignore[override]
        yield {
            "name": page.css("h1::text").get(),
            "page_base_url": page.base_url,
            "base_url": response.base_url,
            "meta_refresh": response.meta_refresh,
        }


@pytest.fixture
def counts(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Any], list[Any]]:
    """Return the lists that every selector extraction pass and every HTML
    metadata read without selector extraction get appended to."""
    passes: list[Any] = []
    metadata_reads: list[Any] = []

    def counting_extract(*args: Any, **kwargs: Any) -> Any:
        passes.append(args)
        return extract(*args, **kwargs)

    def counting_navigation(*args: Any, **kwargs: Any) -> Any:
        metadata_reads.append(args)
        return navigation(*args, **kwargs)

    navigation = frostwork.navigation
    monkeypatch.setattr("web_poet._frostwork._extract", counting_extract)
    monkeypatch.setattr("web_poet.mixins._frostwork_extract", counting_extract)
    monkeypatch.setattr(frostwork, "navigation", counting_navigation)
    return passes, metadata_reads


@pytest.mark.parametrize(
    ("spider_cls", "resource_cls", "refresh_path", "passes_", "metadata_reads_"),
    [
        (MetadataSpider, MetadataHtml, "food/next", 1, 0),
        (MetadataSpider, UndeclaredEncodingHtml, "food/next", 1, 0),
        (MetadataSpider, NoRefreshHtml, None, 1, 0),
        # No selector declarations: Scrapy reads the HTML metadata itself.
        (UndeclaredSpider, MetadataHtml, "food/next", 0, 1),
    ],
)
@deferred_f_from_coro_f
async def test_passes(
    settings: dict[str, Any],
    counts: tuple[list[Any], list[Any]],
    spider_cls: type[scrapy.Spider],
    resource_cls: type[HtmlResource],
    refresh_path: str | None,
    passes_: int,
    metadata_reads_: int,
) -> None:
    items, url, _ = await crawl_items_async(spider_cls, resource_cls, settings)
    meta_refresh = (
        None if refresh_path is None else MetaRefresh(1000.0, url + refresh_path)
    )
    assert items == [
        {
            "name": "Chocolate",
            "page_base_url": f"{url}food/",
            "base_url": f"{url}food/",
            "meta_refresh": meta_refresh,
        }
    ]
    passes, metadata_reads = counts
    assert len(passes) == passes_
    assert len(metadata_reads) == metadata_reads_


@deferred_f_from_coro_f
async def test_no_injection_middleware(
    settings: dict[str, Any], counts: tuple[list[Any], list[Any]]
) -> None:
    settings["ADDONS"] = {}
    settings["DOWNLOADER_MIDDLEWARES"][HtmlMetadataMiddleware] = 585
    items, url, _ = await crawl_items_async(ResponseSpider, MetadataHtml, settings)
    assert items == [
        {
            "base_url": f"{url}food/",
            "meta_refresh": MetaRefresh(1000.0, f"{url}food/next"),
        }
    ]
    passes, metadata_reads = counts
    assert len(passes) == 0
    assert len(metadata_reads) == 1
