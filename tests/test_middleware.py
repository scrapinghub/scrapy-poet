import os
import socket
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional, Union

import andi
import attr
import pytest
import scrapy
from scrapy import Request
from scrapy.http import Response
from scrapy.utils.defer import deferred_f_from_coro_f, maybe_deferred_to_future
from scrapy.utils.log import configure_logging
from twisted.internet.threads import deferToThread
from url_matcher.util import get_domain
from web_poet import ApplyRule, HttpResponse, ItemPage, RequestUrl, ResponseUrl, WebPage
from web_poet.pages import is_injectable

from scrapy_poet import DummyResponse, callback_for
from scrapy_poet.page_input_providers import PageObjectInputProvider
from scrapy_poet.utils.mockserver import MockServer, get_ephemeral_port
from scrapy_poet.utils.testing import (
    EchoResource,
    ProductHtml,
    capture_exceptions,
    crawl_items_async,
    crawl_single_item_async,
)


def spider_for(injectable: type) -> type[scrapy.Spider]:
    class InjectableSpider(scrapy.Spider):
        url: str
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": {
                WithFuturesProvider: 1,
                WithDeferredProvider: 2,
                ExtraClassDataProvider: 3,
            }
        }

        def start_requests(self) -> Iterator[Request]:
            yield Request(self.url, capture_exceptions(callback_for(injectable)))

        async def start(self) -> AsyncIterator[Any]:
            for item_or_request in self.start_requests():
                yield item_or_request

    return InjectableSpider


@attr.s(auto_attribs=True)
class BreadcrumbsExtraction(WebPage[Any]):
    def get(self) -> dict[str, str]:
        return {
            a.css("::text").get(): a.attrib["href"] for a in self.css(".breadcrumbs a")
        }


@attr.s(auto_attribs=True)
class ProductPage(WebPage[Any]):
    breadcrumbs: BreadcrumbsExtraction

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return {
            "url": self.url,
            "name": self.css(".name::text").get(),
            "price": self.xpath('//*[@class="price"]/text()').get(),
            "description": self.css(".description::text").get(),
            "category": " / ".join(self.breadcrumbs.get().keys()),
        }


@attr.s(auto_attribs=True)
class OverridenBreadcrumbsExtraction(WebPage[Any]):
    def get(self) -> dict[str, str]:
        return {"overriden_breadcrumb": "http://example.com"}


@deferred_f_from_coro_f
async def test_basic_case(settings: dict[str, Any]) -> None:
    item, url, _ = await crawl_single_item_async(
        spider_for(ProductPage), ProductHtml, settings
    )
    assert item == {
        "url": url,
        "name": "Chocolate",
        "price": "22€",
        "description": "The best chocolate ever",
        "category": "Food / Sweets",
    }


@deferred_f_from_coro_f
async def test_overrides(settings: dict[str, Any]) -> None:
    host = socket.gethostbyname(socket.gethostname())
    domain = get_domain(host)
    port = get_ephemeral_port()
    settings["SCRAPY_POET_RULES"] = [
        ApplyRule(
            f"{domain}:{port}",
            use=OverridenBreadcrumbsExtraction,
            instead_of=BreadcrumbsExtraction,
        )
    ]
    item, url, _ = await crawl_single_item_async(
        spider_for(ProductPage), ProductHtml, settings, port=port
    )
    assert item == {
        "url": url,
        "name": "Chocolate",
        "price": "22€",
        "description": "The best chocolate ever",
        "category": "overriden_breadcrumb",
    }


@attr.s(auto_attribs=True)
class OptionalAndUnionPageNew(WebPage[Any]):
    breadcrumbs: BreadcrumbsExtraction
    # ruff: disable[UP007,UP045]
    opt_check_1: Optional[BreadcrumbsExtraction]
    union_check_1: Union[BreadcrumbsExtraction, HttpResponse]  # Breadcrumbs is injected
    union_check_2: Union[str, HttpResponse]  # HttpResponse is injected
    union_check_3: Union[Optional[str], HttpResponse]  # HttpResponse is injected
    union_check_4: Union[None, str, HttpResponse]  # HttpResponse is injected
    union_check_5: Union[BreadcrumbsExtraction, None, str]  # Breadcrumbs is injected
    # ruff: enable[UP007,UP045]

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return attr.asdict(self, recurse=False)


@pytest.mark.skipif(
    is_injectable(type(None)),
    reason="This version of web-poet considers type(None) injectable",
)
@deferred_f_from_coro_f
async def test_optional_and_unions_new(settings: dict[str, Any]) -> None:
    item, _, _ = await crawl_single_item_async(
        spider_for(OptionalAndUnionPageNew), ProductHtml, settings
    )
    assert item["breadcrumbs"].response is item["response"]
    assert item["opt_check_1"] is item["breadcrumbs"]
    assert item["union_check_1"] is item["breadcrumbs"]
    assert item["union_check_2"] is item["breadcrumbs"].response
    assert item["union_check_3"] is item["breadcrumbs"].response
    assert item["union_check_4"] is item["breadcrumbs"].response
    assert item["union_check_5"] is item["breadcrumbs"]


@attr.s(auto_attribs=True)
class OptionalAndUnionPageOld(WebPage[Any]):
    breadcrumbs: BreadcrumbsExtraction
    # ruff: disable[UP007,UP045]
    opt_check_1: Optional[BreadcrumbsExtraction]
    opt_check_2: Optional[str]  # str is not Injectable, so None expected here
    union_check_1: Union[BreadcrumbsExtraction, HttpResponse]  # Breadcrumbs is injected
    union_check_2: Union[str, HttpResponse]  # HttpResponse is injected
    union_check_3: Union[Optional[str], HttpResponse]  # None is injected
    union_check_4: Union[None, str, HttpResponse]  # None is injected
    union_check_5: Union[BreadcrumbsExtraction, None, str]  # Breadcrumbs is injected
    # ruff: enable[UP007,UP045]

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return attr.asdict(self, recurse=False)


@pytest.mark.skipif(
    not is_injectable(type(None)),
    reason="This version of web-poet does not consider type(None) injectable",
)
@deferred_f_from_coro_f
async def test_optional_and_unions_old(settings: dict[str, Any]) -> None:
    item, _, _ = await crawl_single_item_async(
        spider_for(OptionalAndUnionPageOld), ProductHtml, settings
    )
    assert item["breadcrumbs"].response is item["response"]
    assert item["opt_check_1"] is item["breadcrumbs"]
    assert item["opt_check_2"] is None
    assert item["union_check_1"] is item["breadcrumbs"]
    assert item["union_check_2"] is item["breadcrumbs"].response
    assert item["union_check_3"] is None
    assert item["union_check_4"] is None
    assert item["union_check_5"] is item["breadcrumbs"]


@attr.s(auto_attribs=True)
class NonInjectablePage(WebPage[Any]):
    a: str | None = None
    b: str = "foo"

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return attr.asdict(self, recurse=False)


@pytest.mark.skipif(
    not hasattr(andi.andi, "_inspect"),
    reason="Before merging https://github.com/scrapinghub/andi/pull/33",
)
@deferred_f_from_coro_f
async def test_non_injectable(settings: dict[str, Any]) -> None:
    item, _, _ = await crawl_single_item_async(
        spider_for(NonInjectablePage), ProductHtml, settings
    )
    assert item["a"] is None
    assert item["b"] == "foo"


@attr.s(auto_attribs=True)
class ProvidedWithDeferred:
    msg: str
    response: HttpResponse | None  # it should be None because this class is provided


@attr.s(auto_attribs=True)
class ProvidedWithFutures(ProvidedWithDeferred):
    pass


class WithDeferredProvider(PageObjectInputProvider):
    provided_classes = {ProvidedWithDeferred}

    async def __call__(
        self, to_provide: set[Callable[..., Any]], response: scrapy.http.Response
    ) -> list[Any]:
        five = await maybe_deferred_to_future(deferToThread(lambda: 5))
        return [ProvidedWithDeferred(f"Provided {five}!", None)]


class WithFuturesProvider(PageObjectInputProvider):
    provided_classes = {ProvidedWithFutures}

    async def async_fn(self) -> int:
        return 5

    async def __call__(self, to_provide: set[Callable[..., Any]]) -> list[Any]:
        five = await self.async_fn()
        return [ProvidedWithFutures(f"Provided {five}!", None)]


@attr.s(auto_attribs=True)
class ExtraClassData(ItemPage[Any]):
    msg: str

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return {"msg": self.msg}


class ExtraClassDataProvider(PageObjectInputProvider):
    provided_classes = {ExtraClassData}

    def __call__(self, to_provide: set[Callable[..., Any]]) -> dict[type, Any]:
        # This should generate a runtime error in Injection Middleware because
        # we're returning a class that's not listed in self.provided_classes
        return {
            ExtraClassData: ExtraClassData("this should be returned"),
            HttpResponse: HttpResponse("example.com", b"this shouldn't"),
        }


@attr.s(auto_attribs=True)
class ProvidedWithDeferredPage(WebPage[Any]):
    provided: ProvidedWithDeferred

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return attr.asdict(self, recurse=False)


@attr.s(auto_attribs=True)
class ProvidedWithFuturesPage(ProvidedWithDeferredPage):
    provided: ProvidedWithFutures


@pytest.mark.parametrize("type_", [ProvidedWithDeferredPage, ProvidedWithFuturesPage])
@deferred_f_from_coro_f
async def test_providers(settings: dict[str, Any], type_: type) -> None:
    item, _, _ = await crawl_single_item_async(spider_for(type_), ProductHtml, settings)
    assert item["provided"].msg == "Provided 5!"
    assert item["provided"].response is None


@deferred_f_from_coro_f
async def test_providers_returning_wrong_classes(
    settings: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Injection Middleware should raise a runtime error whenever a provider
    returns instances of classes that they're not supposed to provide.
    """
    await crawl_single_item_async(spider_for(ExtraClassData), ProductHtml, settings)
    assert "UndeclaredProvidedTypeError:" in caplog.text


class MultiArgsCallbackSpiderNew(scrapy.Spider):
    url: str
    custom_settings = {"SCRAPY_POET_PROVIDERS": {WithDeferredProvider: 1}}

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            self.url, self.parse, cb_kwargs={"cb_arg": "arg!", "cb_arg2": False}
        )

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(
        self,
        response: Response,
        product: ProductPage,
        provided: ProvidedWithDeferred,
        cb_arg: str | None,
        cb_arg2: bool | None,
        non_cb_arg: str | None = "default",
    ) -> Iterator[dict[str, Any]]:
        yield {
            "product": product,
            "provided": provided,
            "cb_arg": cb_arg,
            "cb_arg2": cb_arg2,
            "non_cb_arg": non_cb_arg,
        }


@pytest.mark.skipif(
    is_injectable(type(None)),
    reason="This version of web-poet considers type(None) injectable",
)
@deferred_f_from_coro_f
async def test_multi_args_callbacks_new(settings: dict[str, Any]) -> None:
    item, _, _ = await crawl_single_item_async(
        MultiArgsCallbackSpiderNew, ProductHtml, settings
    )
    assert type(item["product"]) is ProductPage
    assert type(item["provided"]) is ProvidedWithDeferred
    assert item["cb_arg"] == "arg!"
    assert item["cb_arg2"] is False
    assert item["non_cb_arg"] == "default"


class MultiArgsCallbackSpiderOld(scrapy.Spider):
    url: str
    custom_settings = {"SCRAPY_POET_PROVIDERS": {WithDeferredProvider: 1}}

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            self.url, self.parse, cb_kwargs={"cb_arg": "arg!", "cb_arg2": False}
        )

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(
        self,
        response: Response,
        product: ProductPage,
        provided: ProvidedWithDeferred,
        cb_arg: Optional[str],  # noqa: UP045
        cb_arg2: Optional[bool],  # noqa: UP045
        non_cb_arg: Optional[str],  # noqa: UP045
    ) -> Iterator[dict[str, Any]]:
        yield {
            "product": product,
            "provided": provided,
            "cb_arg": cb_arg,
            "cb_arg2": cb_arg2,
            "non_cb_arg": non_cb_arg,
        }


@pytest.mark.skipif(
    not is_injectable(type(None)),
    reason="This version of web-poet does not consider type(None) injectable",
)
@deferred_f_from_coro_f
async def test_multi_args_callbacks_old(settings: dict[str, Any]) -> None:
    item, _, _ = await crawl_single_item_async(
        MultiArgsCallbackSpiderOld, ProductHtml, settings
    )
    assert type(item["product"]) is ProductPage
    assert type(item["provided"]) is ProvidedWithDeferred
    assert item["cb_arg"] == "arg!"
    assert item["cb_arg2"] is False
    assert item["non_cb_arg"] is None


@attr.s(auto_attribs=True)
class UnressolvableProductPage(ProductPage):
    this_is_unresolvable: str


@deferred_f_from_coro_f
async def test_injection_failure(settings: dict[str, Any]) -> None:
    configure_logging(settings)
    items, *_ = await crawl_items_async(
        spider_for(UnressolvableProductPage), ProductHtml, settings
    )
    assert items == []


class MySpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: Response) -> dict[str, Any]:
        return {
            "response": response,
        }


class SkipDownloadSpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)  # type: ignore[arg-type]

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: DummyResponse) -> dict[str, Any]:  # type: ignore[override]
        return {
            "response": response,
        }


@deferred_f_from_coro_f
async def test_skip_downloads(settings: dict[str, Any]) -> None:
    item, _, crawler = await crawl_single_item_async(MySpider, ProductHtml, settings)
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is False
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1

    item, _, crawler = await crawl_single_item_async(
        SkipDownloadSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is True
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 0


class RequestUrlSpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)  # type: ignore[arg-type]

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: DummyResponse, url: RequestUrl) -> dict[str, Any]:  # type: ignore[override]
        return {
            "response": response,
            "url": url,
        }


@deferred_f_from_coro_f
async def test_skip_download_request_url(settings: dict[str, Any]) -> None:
    item, url, crawler = await crawl_single_item_async(
        RequestUrlSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    assert isinstance(item["response"], DummyResponse) is True
    assert isinstance(item["url"], RequestUrl)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 0


class ResponseUrlSpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)  # type: ignore[arg-type]

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: DummyResponse, url: ResponseUrl) -> dict[str, Any]:  # type: ignore[override]
        return {
            "response": response,
            "url": url,
        }


@deferred_f_from_coro_f
async def test_skip_download_response_url(settings: dict[str, Any]) -> None:
    item, url, crawler = await crawl_single_item_async(
        ResponseUrlSpider, ProductHtml, settings
    )
    assert isinstance(item["response"], Response) is True
    # Even if the spider marked the response with DummyResponse, the response
    # is still needed since ResponseUrl depends on it.
    assert isinstance(item["response"], DummyResponse) is False
    assert isinstance(item["url"], ResponseUrl)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 1


@attr.s(auto_attribs=True)
class ResponseUrlPage(WebPage[Any]):
    response_url: ResponseUrl

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return {"response_url": self.response_url}


class ResponseUrlPageSpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)  # type: ignore[arg-type]

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: DummyResponse, page: ResponseUrlPage) -> dict[str, Any]:  # type: ignore[override]
        return page.to_item()


@deferred_f_from_coro_f
async def test_skip_download_response_url_page(settings: dict[str, Any]) -> None:
    item, url, crawler = await crawl_single_item_async(
        ResponseUrlPageSpider, ProductHtml, settings
    )
    assert tuple(item.keys()) == ("response_url",)
    assert str(item["response_url"]) == url
    # Even if the spider marked the response with DummyResponse, the response
    # is still needed since ResponseUrl depends on it.
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 1
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 0


@attr.s(auto_attribs=True)
class RequestUrlPage(ItemPage[Any]):
    url: RequestUrl

    def to_item(self) -> dict[str, Any]:  # type: ignore[override]
        return {"url": self.url}


class RequestUrlPageSpider(scrapy.Spider):
    url: str

    def start_requests(self) -> Iterator[Request]:
        yield Request(url=self.url, callback=self.parse)  # type: ignore[arg-type]

    async def start(self) -> AsyncIterator[Any]:
        for item_or_request in self.start_requests():
            yield item_or_request

    def parse(self, response: DummyResponse, page: RequestUrlPage) -> dict[str, Any]:  # type: ignore[override]
        return page.to_item()


@deferred_f_from_coro_f
async def test_skip_download_request_url_page(settings: dict[str, Any]) -> None:
    item, url, crawler = await crawl_single_item_async(
        RequestUrlPageSpider, ProductHtml, settings
    )
    assert tuple(item.keys()) == ("url",)
    assert str(item["url"]) == url
    assert crawler.stats.get_stats().get("downloader/request_count", 0) == 0
    assert crawler.stats.get_stats().get("scrapy_poet/dummy_response_count", 0) == 1
    assert crawler.stats.get_stats().get("downloader/response_count", 0) == 0


def test_scrapy_shell(tmp_path: Path) -> None:
    try:
        import scrapy.addons  # noqa: F401,PLC0415
    except ImportError:
        settings = """
            DOWNLOADER_MIDDLEWARES = {
                "scrapy_poet.InjectionMiddleware": 543,
                "scrapy.downloadermiddlewares.stats.DownloaderStats": None,
                "scrapy_poet.DownloaderStatsMiddleware": 850,
            }
            REQUEST_FINGERPRINTER_CLASS = "scrapy_poet.ScrapyPoetRequestFingerprinter"
            SPIDER_MIDDLEWARES = {
                "scrapy_poet.RetryMiddleware": 275,
            }
        """
    else:
        settings = """
            ADDONS = {
                "scrapy_poet.Addon": 300,
            }
        """
    settings = dedent(settings)
    (tmp_path / "settings.py").write_text(settings)

    env = os.environ.copy()
    env["SCRAPY_SETTINGS_MODULE"] = "settings"
    with MockServer(EchoResource) as server:
        args = (
            sys.executable,
            "-m",
            "scrapy.cmdline",
            "shell",
            server.root_url,
            "-c",
            "item",
        )
        p = subprocess.Popen(
            args,
            cwd=tmp_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            out, err = p.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            pytest.fail("Command took too much time to complete")

    assert b"Using DummyResponse instead of downloading" not in err
    assert b"{}" in out
