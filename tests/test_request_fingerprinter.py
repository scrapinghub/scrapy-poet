from collections.abc import Callable, Iterable
from importlib.metadata import version as package_version
from itertools import combinations
from typing import TYPE_CHECKING, Annotated, Any, Set, cast
from unittest.mock import patch

import pytest
from packaging.version import Version
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.utils.misc import load_object
from web_poet import (
    BrowserHtml,
    BrowserResponse,
    HttpClient,
    HttpRequest,
    HttpRequestBody,
    HttpRequestHeaders,
    HttpResponse,
    HttpResponseBody,
    HttpResponseHeaders,
    ItemPage,
    PageParams,
    RequestUrl,
    ResponseUrl,
    RulesRegistry,
    Stats,
    WebPage,
)

from scrapy_poet import DummyResponse
from scrapy_poet._request_fingerprinter import _serialize_dep
from scrapy_poet.downloadermiddlewares import DEFAULT_PROVIDERS
from scrapy_poet.injection import Injector, is_class_provided_by_any_provider_fn
from scrapy_poet.page_input_providers import PageObjectInputProvider
from scrapy_poet.utils.testing import _get_test_settings
from scrapy_poet.utils.testing import get_crawler as _get_crawler

if TYPE_CHECKING:
    from scrapy_poet import ScrapyPoetRequestFingerprinter

ANDI_VERSION = Version(package_version("andi"))

SETTINGS = _get_test_settings()

try:
    import scrapy.addons  # noqa: F401
except ImportError:
    ADDON_SUPPORT = False
else:
    ADDON_SUPPORT = True


def get_crawler(
    spider_cls: type[Spider] | None = None,
    settings: dict[str, Any] | None = None,
    ensure_providers_for: Iterable[Any] | None = None,
) -> Crawler:
    settings = {**SETTINGS} if settings is None else settings

    kwargs: dict[str, Any] = {}
    if spider_cls is not None:
        kwargs["spider_cls"] = spider_cls

    ensure_providers_for = ensure_providers_for or ()
    if ensure_providers_for:
        dummy_providers = get_dummy_providers(*ensure_providers_for)
        if dummy_providers:
            settings["SCRAPY_POET_PROVIDERS"] = dict.fromkeys(dummy_providers, 0)

    return _get_crawler(settings=settings, **kwargs)


dummy_injector = Injector(crawler=get_crawler())
default_providers = [load_object(cls)(dummy_injector) for cls in DEFAULT_PROVIDERS]
is_class_provided_by_any_default_provider = is_class_provided_by_any_provider_fn(
    default_providers
)


def get_dummy_providers(*input_classes: Any) -> list[type[PageObjectInputProvider]]:
    dummy_providers: list[type[PageObjectInputProvider]] = []

    for input_cls in input_classes:
        if is_class_provided_by_any_default_provider(input_cls):
            continue

        class DummyProvider(PageObjectInputProvider):
            provided_classes = {input_cls}

            def __call__(self, to_provide: Set[Callable[..., Any]]) -> list[Any]:
                input_cls = next(iter(self.provided_classes))
                return [input_cls()]

        dummy_providers.append(DummyProvider)

    return dummy_providers


def test_single_callback() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response: Response, page: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_page)
    fingerprint2 = fingerprinter.fingerprint(request2)
    request3 = Request("https://toscrape.com", callback=spider.parse_page)
    fingerprint3 = fingerprinter.fingerprint(request3)
    request4 = Request("https://books.toscrape.com", callback=spider.parse_page)
    fingerprint4 = fingerprinter.fingerprint(request4)
    assert fingerprint1 != fingerprint2  # same url, no deps vs deps
    assert fingerprint2 == fingerprint3  # same url, same callback
    assert fingerprint2 != fingerprint4  # different url, same callback


def test_same_deps_different_callbacks() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response: Response, a: WebPage) -> None:  # type: ignore[type-arg]
            pass

        async def parse_b(self, response: Response, b: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_same_deps_different_order() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response: Response, a: WebPage, b: ItemPage) -> None:  # type: ignore[type-arg]
            pass

        async def parse_b(self, response: Response, a: ItemPage, b: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_different_deps() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_item(self, response: Response, item: ItemPage) -> None:  # type: ignore[type-arg]
            pass

        async def parse_web(self, response: Response, web: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_item)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_web)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


def test_response_typing() -> None:
    """The type of the response parameter is ignored, even when it is
    DummyResponse. It’s the other injected parameters that should alter the
    fingerprint."""

    class TestSpider(Spider):
        name = "test_spider"

        async def parse_untyped(self, response, web: WebPage) -> None:  # type: ignore[no-untyped-def,type-arg]
            pass

        async def parse_typed(self, response: Response, web: WebPage) -> None:  # type: ignore[type-arg]
            pass

        async def parse_dummy(self, response: DummyResponse, web: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_untyped)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_typed)
    fingerprint2 = fingerprinter.fingerprint(request2)
    request3 = Request("https://toscrape.com", callback=spider.parse_dummy)  # type: ignore[arg-type]
    fingerprint3 = fingerprinter.fingerprint(request3)
    assert fingerprint1 == fingerprint2
    assert fingerprint1 == fingerprint3


@pytest.mark.parametrize(
    "input_cls",
    [
        HttpClient,
        HttpRequest,
        HttpRequestBody,
        HttpRequestHeaders,
        PageParams,
        RequestUrl,
        Stats,
    ],
)
def test_ignored_unannotated_page_inputs(input_cls: type) -> None:
    """These web-poet page input classes, unless annotated, cannot have any
    bearing on the request on their own, so they should not alter the request
    fingerprint."""

    class TestSpider(Spider):
        name = "test_spider"

        async def parse_input(self, response: Response, some_input: input_cls) -> None:  # type: ignore[valid-type]
            pass

    crawler = get_crawler(spider_cls=TestSpider, ensure_providers_for=[input_cls])

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_input)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


# Inputs that affect the fingerprint.
#
# We do not try to be smart. e.g. although ResponseUrl should always be
# available, that could technically not be the case given a custom user
# provider.
FINGERPRINTING_INPUTS = (
    BrowserHtml,
    BrowserResponse,
    HttpResponse,
    HttpResponseBody,
    HttpResponseHeaders,
    ResponseUrl,
)


@pytest.mark.parametrize("input_cls", FINGERPRINTING_INPUTS)
def test_fingerprinting_unannotated_page_inputs(input_cls: type) -> None:
    """Inputs that may have an impact on the actual request sent even without
    annotations."""

    class TestSpider(Spider):
        name = "test_spider"

        async def parse_input(self, response: Response, some_input: input_cls) -> None:  # type: ignore[valid-type]
            pass

    crawler = get_crawler(spider_cls=TestSpider, ensure_providers_for=[input_cls])

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_input)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


@pytest.mark.parametrize(
    ("input_cls_a", "input_cls_b"),
    (tuple(combination) for combination in combinations(FINGERPRINTING_INPUTS, 2)),
)
def test_fingerprinting_unannotated_page_input_combinations(
    input_cls_a: type, input_cls_b: type
) -> None:
    """Make sure that a combination of known inputs that alter the request
    fingerprint does not result in the same fingerprint."""

    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response: Response, input_a: input_cls_a) -> None:  # type: ignore[valid-type]
            pass

        async def parse_b(self, response: Response, input_b: input_cls_b) -> None:  # type: ignore[valid-type]
            pass

        async def parse_all(
            self,
            response: Response,
            input_a: input_cls_a,  # type: ignore[valid-type]
            input_b: input_cls_b,  # type: ignore[valid-type]
        ) -> None:
            pass

    crawler = get_crawler(
        spider_cls=TestSpider, ensure_providers_for=[input_cls_a, input_cls_b]
    )

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    request3 = Request("https://toscrape.com", callback=spider.parse_all)
    fingerprint3 = fingerprinter.fingerprint(request3)
    assert fingerprint1 != fingerprint2
    assert fingerprint1 != fingerprint3
    assert fingerprint2 != fingerprint3


def test_dep_resolution() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response: Response, web: WebPage) -> None:  # type: ignore[type-arg]
            pass

        async def parse_b(
            self,
            response: Response,
            web: WebPage,  # type: ignore[type-arg]
            http_response: HttpResponse,
        ) -> None:
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_page_params(caplog: pytest.LogCaptureFixture) -> None:
    Unserializable = object()

    crawler = get_crawler()
    fingerprinter = crawler.request_fingerprinter

    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)

    request2 = Request("https://toscrape.com", meta={"page_params": {"a": "1"}})
    fingerprint2 = fingerprinter.fingerprint(request2)

    request3 = Request("https://toscrape.com", meta={"page_params": {"a": "2"}})
    fingerprint3 = fingerprinter.fingerprint(request3)

    request4 = Request(
        "https://toscrape.com", meta={"page_params": {"a": "2"}, "foo": "bar"}
    )
    fingerprint4 = fingerprinter.fingerprint(request4)

    request5 = Request(
        "https://toscrape.com", meta={"page_params": {"a": Unserializable}}
    )
    assert "Cannot serialize page params" not in caplog.text
    caplog.clear()
    fingerprint5 = fingerprinter.fingerprint(request5)
    assert "Cannot serialize page params" in caplog.text

    assert fingerprint1 != fingerprint2
    assert fingerprint1 != fingerprint3
    assert fingerprint2 != fingerprint3
    assert fingerprint3 == fingerprint4
    assert fingerprint1 == fingerprint5


@pytest.mark.parametrize(
    "meta",
    [
        {},
        {"page_params": None},
        {"page_params": {}},
        {"foo": "bar"},
        {"foo": "bar", "page_params": None},
        {"foo": "bar", "page_params": {}},
    ],
)
def test_meta(meta: dict[str, Any]) -> None:
    crawler = get_crawler()
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", meta=meta)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


@pytest.mark.skipif(
    ANDI_VERSION <= Version("0.4.1"),
    reason="https://github.com/scrapinghub/andi/pull/25",
)
def test_different_annotations() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response: Response, a: Annotated[WebPage, "a"]) -> None:  # type: ignore[type-arg]
            pass

        async def parse_b(self, response: Response, b: Annotated[WebPage, "b"]) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


def test_serialize_dep() -> None:
    assert _serialize_dep(HttpResponse) == "web_poet.page_inputs.http.HttpResponse"


def test_serialize_dep_annotated() -> None:
    assert (
        _serialize_dep(Annotated[HttpResponse, "foo"])
        == "web_poet.page_inputs.http.HttpResponse['foo']"
    )


def test_base_default() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response: Response, page: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = cast(
        "ScrapyPoetRequestFingerprinter", crawler.request_fingerprinter
    )
    base_fingerprinter = fingerprinter._base_request_fingerprinter

    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    base_fingerprint = base_fingerprinter.fingerprint(request1)
    assert fingerprint1 == base_fingerprint

    request2 = Request("https://toscrape.com", callback=spider.parse_page)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert base_fingerprint == base_fingerprinter.fingerprint(request2)
    assert fingerprint2 != base_fingerprint


def test_base_custom() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response: Response, page: WebPage) -> None:  # type: ignore[type-arg]
            pass

    class CustomFingerprinter:
        def fingerprint(self, request: Request) -> bytes:
            return b"foo"

    settings = {
        **SETTINGS,
        "SCRAPY_POET_REQUEST_FINGERPRINTER_BASE_CLASS": CustomFingerprinter,
    }
    crawler = get_crawler(spider_cls=TestSpider, settings=settings)
    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter

    request = Request("https://example.com")
    assert fingerprinter.fingerprint(request) == b"foo"
    request = Request("https://example.com", callback=spider.parse_page)
    assert fingerprinter.fingerprint(request) != b"foo"


@pytest.mark.skipif(ADDON_SUPPORT, reason="Using the add-on")
def test_missing_middleware() -> None:
    settings = {**SETTINGS, "DOWNLOADER_MIDDLEWARES": {}}
    crawler = get_crawler(settings=settings)
    fingerprinter = crawler.request_fingerprinter
    request = Request("https://example.com")
    with pytest.raises(RuntimeError):
        fingerprinter.fingerprint(request)


def test_callback_cache() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response: Response, page: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = cast(
        "ScrapyPoetRequestFingerprinter", crawler.request_fingerprinter
    )
    to_wrap = fingerprinter._get_deps
    request1 = Request("https://example.com", callback=spider.parse_page)
    request2 = Request("https://toscrape.com", callback=spider.parse_page)
    with patch.object(fingerprinter, "_get_deps", wraps=to_wrap) as mock:
        fingerprinter.fingerprint(request1)
        fingerprinter.fingerprint(request2)
        mock.assert_called_once_with(request1)


def test_request_cache() -> None:
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response: Response, page: WebPage) -> None:  # type: ignore[type-arg]
            pass

    crawler = get_crawler(spider_cls=TestSpider)

    spider = cast("TestSpider", crawler.spider)
    fingerprinter = cast(
        "ScrapyPoetRequestFingerprinter", crawler.request_fingerprinter
    )
    base_fingerprinter = fingerprinter._base_request_fingerprinter
    to_wrap = base_fingerprinter.fingerprint
    request = Request("https://example.com", callback=spider.parse_page)
    with patch.object(base_fingerprinter, "fingerprint", wraps=to_wrap) as mock:
        fingerprinter.fingerprint(request)
        fingerprinter.fingerprint(request)
        mock.assert_called_once_with(request)


def test_item(settings: dict[str, Any]) -> None:
    """Test that fingerprinting works even for items."""
    registry = RulesRegistry()

    class MyItem:
        pass

    @registry.handle_urls("example.com")
    class MyPage(ItemPage[MyItem]):
        pass

    class TestSpider(Spider):
        name = "test"

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.request = Request("https://example.com", callback=self.parse_page)

        async def parse_page(self, response: Response, a: MyItem) -> None:
            pass

    settings["SCRAPY_POET_RULES"] = registry.get_rules()
    crawler = get_crawler(spider_cls=TestSpider, settings=settings)
    spider = cast("TestSpider", crawler.spider)
    fingerprinter = crawler.request_fingerprinter

    fingerprint = fingerprinter.fingerprint(spider.request)
    assert fingerprint
    assert isinstance(fingerprint, bytes)
