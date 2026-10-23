from collections.abc import AsyncIterator
from typing import Any

import attrs
import pytest
import scrapy
from scrapy.http import TextResponse
from scrapy.utils.defer import deferred_f_from_coro_f
from web_poet import WebPage, field

from scrapy_poet.utils.testing import HtmlResource, crawl_items_async

# web-poet and Scrapy with frostwork navigation.
pytest.importorskip("web_poet._frostwork")
if not hasattr(TextResponse, "meta_refresh"):
    pytest.skip("Scrapy without TextResponse.meta_refresh", allow_module_level=True)

import frostwork
from web_poet import css_get
from web_poet._frostwork import _extract as extract


class NavigationHtml(HtmlResource):
    content_type = "text/html; charset=utf-8"
    html = """
    <html>
        <base href="/food/">
        <meta http-equiv="refresh" content="1000; url=next">
        <h1>Chocolate</h1>
    </html>
    """


class UndeclaredEncodingHtml(NavigationHtml):
    content_type = "text/html"


@attrs.define
class NamePage(WebPage[Any]):
    name = field(css_get("h1::text"))


@attrs.define
class UndeclaredPage(WebPage[Any]):
    pass


class NavigationSpider(scrapy.Spider):
    name = "navigation"
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


class UndeclaredSpider(NavigationSpider):
    async def parse_page(self, response: Any, page: UndeclaredPage) -> Any:  # type: ignore[override]
        yield {
            "name": page.css("h1::text").get(),
            "page_base_url": page.base_url,
            "base_url": response.base_url,
            "meta_refresh": response.meta_refresh,
        }


@pytest.mark.parametrize(
    ("spider_cls", "resource_cls", "passes_", "navigations"),
    [
        (NavigationSpider, NavigationHtml, 1, 0),
        # Scrapy and web-poet infer different encodings, so web-poet
        # extracts again.
        (NavigationSpider, UndeclaredEncodingHtml, 2, 0),
        # No selector declarations: Scrapy reads the navigation itself.
        (UndeclaredSpider, NavigationHtml, 0, 1),
    ],
)
@deferred_f_from_coro_f
async def test_passes(
    settings: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    spider_cls: type[scrapy.Spider],
    resource_cls: type[HtmlResource],
    passes_: int,
    navigations: int,
) -> None:
    passes: list[Any] = []
    navigation_calls: list[Any] = []

    def counting_extract(*args: Any, **kwargs: Any) -> Any:
        passes.append(args)
        return extract(*args, **kwargs)

    def counting_navigation(*args: Any, **kwargs: Any) -> Any:
        navigation_calls.append(args)
        return navigation(*args, **kwargs)

    navigation = frostwork.navigation
    monkeypatch.setattr("scrapy_poet.downloadermiddlewares._extract", counting_extract)
    monkeypatch.setattr("web_poet.mixins._frostwork_extract", counting_extract)
    monkeypatch.setattr(frostwork, "navigation", counting_navigation)

    items, url, _ = await crawl_items_async(spider_cls, resource_cls, settings)
    assert items == [
        {
            "name": "Chocolate",
            "page_base_url": f"{url}/food/",
            "base_url": f"{url}/food/",
            "meta_refresh": (1000.0, f"{url}/food/next"),
        }
    ]
    assert len(passes) == passes_
    assert len(navigation_calls) == navigations
