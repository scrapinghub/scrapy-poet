from __future__ import annotations

import contextlib
import json
from inspect import isasyncgenfunction
from typing import TYPE_CHECKING, Any
from warnings import warn

from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import CloseSpider
from scrapy.settings import Settings
from scrapy.utils.defer import maybe_deferred_to_future
from scrapy.utils.python import to_bytes
from scrapy.utils.test import get_crawler as _get_crawler
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from scrapy_poet import ScrapyPoetRequestFingerprinter
from scrapy_poet.utils.mockserver import MockServer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Generator

    from scrapy.http import Request, Response
    from scrapy.settings import BaseSettings
    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure
    from twisted.web.server import Request as TwistedRequest
    from typing_extensions import Self


class HtmlResource(Resource):
    isLeaf = True
    content_type = "text/html"
    html = ""
    extra_headers: dict[str, str] = {}
    status_code = 200

    def render_GET(self, request: TwistedRequest) -> bytes:
        request.setHeader(b"content-type", to_bytes(self.content_type))
        for name, value in self.extra_headers.items():
            request.setHeader(to_bytes(name), to_bytes(value))
        request.setResponseCode(self.status_code)
        return to_bytes(self.html)


class LeafResource(Resource):
    isLeaf = True

    def deferRequest(
        self,
        request: TwistedRequest,
        delay: float,
        f: Callable[..., Any],
        *a: Any,
        **kw: Any,
    ) -> Deferred[Any]:
        from twisted.internet import reactor

        def _cancelrequest(_: Failure) -> None:
            # silence CancelledError
            d.addErrback(lambda _: None)
            d.cancel()

        d = deferLater(reactor, delay, f, *a, **kw)
        request.notifyFinish().addErrback(_cancelrequest)
        return d


class DelayedResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> int:
        assert request.content
        decoded_body = request.content.read().decode()
        seconds = float(decoded_body) if decoded_body else 0
        self.deferRequest(
            request,
            seconds,
            self._delayedRender,
            request,
            seconds,
        )
        return NOT_DONE_YET

    def _delayedRender(self, request: TwistedRequest, seconds: float) -> None:
        request.finish()


class EchoResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> bytes:
        assert request.content
        content: bytes = request.content.read()
        return content


class HeadersResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> bytes:
        return json.dumps(
            {
                k.decode(): [v.decode() for v in vs]
                for k, vs in request.requestHeaders.getAllRawHeaders()
            }
        ).encode()


class StatusResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> bytes:
        assert request.content
        decoded_body = request.content.read().decode()
        if decoded_body:
            request.setResponseCode(int(decoded_body))
        return b""


class ForbiddenResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> bytes:
        request.setResponseCode(403)
        return b""


class DropResource(LeafResource):
    def render_GET(self, request: TwistedRequest) -> int:
        request.setHeader(b"Content-Length", b"10")
        try:
            assert request.channel.transport
            request.channel.transport.loseConnection()  # type: ignore[misc]
        finally:
            request.finish()
        return NOT_DONE_YET


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


@inlineCallbacks
def crawl_items(
    spider_cls: type[Spider],
    resource_cls: type[Resource],
    settings: dict[str, Any] | BaseSettings | None,
    spider_kwargs: dict[str, Any] | None = None,
    port: int | None = None,
) -> Generator[Deferred[Any], Any, tuple[list[Any], str, Crawler]]:
    """Use spider_cls to crawl resource_cls. URL of the resource is passed
    to the spider as ``url`` argument.
    Return ``(items, resource_url, crawler)`` tuple.
    """
    warn(
        "crawl_items is deprecated; use crawl_items_async instead",
        DeprecationWarning,
        stacklevel=2,
    )
    spider_kwargs = {} if spider_kwargs is None else spider_kwargs
    crawler = make_crawler(spider_cls, settings)
    with MockServer(resource_cls, port=port) as s:
        root_url = s.root_url
        yield crawler.crawl(url=root_url, **spider_kwargs)
    return crawler.spider.collected_items, s.root_url, crawler  # type: ignore[union-attr]


async def crawl_items_async(
    spider_cls: type[Spider],
    resource_cls: type[Resource],
    settings: dict[str, Any] | BaseSettings | None,
    spider_kwargs: dict[str, Any] | None = None,
    port: int | None = None,
) -> tuple[list[Any], str, Crawler]:
    """Use spider_cls to crawl resource_cls. URL of the resource is passed
    to the spider as ``url`` argument.
    Return ``(items, resource_url, crawler)`` tuple.
    """
    spider_kwargs = {} if spider_kwargs is None else spider_kwargs
    crawler = make_crawler(spider_cls, settings)
    with MockServer(resource_cls, port=port) as s:
        root_url = s.root_url
        await maybe_deferred_to_future(crawler.crawl(url=root_url, **spider_kwargs))
    return crawler.spider.collected_items, s.root_url, crawler  # type: ignore[union-attr]


@inlineCallbacks
def crawl_single_item(
    spider_cls: type[Spider],
    resource_cls: type[Resource],
    settings: dict[str, Any] | BaseSettings | None,
    spider_kwargs: dict[str, Any] | None = None,
    port: int | None = None,
) -> Generator[Deferred[Any], Any, tuple[Any, str, Crawler]]:
    """Run a spider where a single item is expected. Use in combination with
    ``capture_exceptions`` and ``CollectorPipeline``
    """
    warn(
        "crawl_single_item is deprecated; use crawl_single_item_async instead",
        DeprecationWarning,
        stacklevel=2,
    )
    items, url, crawler = yield crawl_items(
        spider_cls, resource_cls, settings, spider_kwargs=spider_kwargs, port=port
    )
    try:
        item = items[0]
    except IndexError:
        return None, url, crawler

    if isinstance(item, dict) and "exception" in item:
        raise item["exception"]
    return item, url, crawler


async def crawl_single_item_async(
    spider_cls: type[Spider],
    resource_cls: type[Resource],
    settings: dict[str, Any] | BaseSettings | None,
    spider_kwargs: dict[str, Any] | None = None,
    port: int | None = None,
) -> tuple[Any, str, Crawler]:
    """Run a spider where a single item is expected. Use in combination with
    ``capture_exceptions`` and ``CollectorPipeline``
    """
    items, url, crawler = await crawl_items_async(
        spider_cls, resource_cls, settings, spider_kwargs=spider_kwargs, port=port
    )
    try:
        item = items[0]
    except IndexError:
        return None, url, crawler

    if isinstance(item, dict) and "exception" in item:
        raise item["exception"]
    return item, url, crawler


def get_download_handler(crawler: Crawler, schema: str) -> Any:
    assert crawler.engine
    return crawler.engine.downloader.handlers._get_handler(schema)


def make_crawler(
    spider_cls: type[Spider], settings: dict[str, Any] | BaseSettings | None = None
) -> Crawler:
    settings = settings or {}
    if isinstance(settings, dict):
        settings = {**_get_test_settings(), **settings}
    else:
        user_settings = settings
        settings = Settings(_get_test_settings())
        for k, v in dict(user_settings).items():
            priority = user_settings.getpriority(k)
            assert priority is not None
            settings.set(k, v, priority=priority)

    if not getattr(spider_cls, "name", None):

        class Spider(spider_cls):  # type: ignore[valid-type, misc]
            name = "test_spider"

        Spider.__name__ = spider_cls.__name__
        Spider.__module__ = spider_cls.__module__
        spider_cls = Spider
    return Crawler(spider_cls, settings)


def setup_crawler_engine(crawler: Crawler) -> None:
    """Run the crawl steps until engine setup, so that crawler.engine is not
    None.
    https://github.com/scrapy/scrapy/blob/8fbebfa943c3352f5ba49f46531a6ccdd0b52b60/scrapy/crawler.py#L116-L122
    """

    crawler.crawling = True
    crawler.spider = crawler._create_spider()
    crawler.settings.frozen = False
    with contextlib.suppress(AttributeError):  # Scrapy < 2.10
        crawler._apply_settings()
    crawler.engine = crawler._create_engine()

    handler = get_download_handler(crawler, "https")
    if hasattr(handler, "engine_started"):
        handler.engine_started()


class DummySpider(Spider):
    name = "dummy"


def get_crawler(
    settings: dict[str, Any] | None = None,
    spider_cls: type[Spider] = DummySpider,
    setup_engine: bool = True,
) -> Crawler:
    settings = settings or {}
    crawler = _get_crawler(settings_dict=settings, spidercls=spider_cls)
    if setup_engine:
        setup_crawler_engine(crawler)
    return crawler


class CollectorPipeline:
    crawler: Crawler

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        obj = cls()
        obj.crawler = crawler
        return obj

    def open_spider(self, spider: Spider | None = None) -> None:
        self.crawler.spider.collected_items = []  # type: ignore[union-attr]

    def process_item(self, item: Any, spider: Spider | None = None) -> Any:
        self.crawler.spider.collected_items.append(item)  # type: ignore[union-attr]
        return item


class InjectedDependenciesCollectorMiddleware:
    crawler: Crawler

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        obj = cls()
        obj.crawler = crawler
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        return obj

    def spider_opened(self, spider: Spider | None = None) -> None:
        self.crawler.spider.collected_response_deps = []  # type: ignore[union-attr]

    def process_response(
        self, request: Request, response: Response, spider: Spider | None = None
    ) -> Response:
        self.crawler.spider.collected_response_deps.append(request.cb_kwargs)  # type: ignore[union-attr]
        return response


def _get_test_settings() -> dict[str, Any]:
    settings: dict[str, Any] = {
        # collect scraped items to crawler.spider.collected_items
        "ITEM_PIPELINES": {
            CollectorPipeline: 100,
        },
        "DOWNLOADER_MIDDLEWARES": {
            # collect injected dependencies to crawler.spider.collected_response_deps
            InjectedDependenciesCollectorMiddleware: 542,
        },
        # Scrapy 2.19+ logs a warning when the default reactor keeps this
        # extension from loading, which breaks tests asserting an empty log.
        "REMOTE_CONTROL_ENABLED": False,
    }
    try:
        import scrapy.addons  # noqa: F401,PLC0415
    except ImportError:
        settings["DOWNLOADER_MIDDLEWARES"]["scrapy_poet.InjectionMiddleware"] = 543
        settings["DOWNLOADER_MIDDLEWARES"][
            "scrapy.downloadermiddlewares.stats.DownloaderStats"
        ] = None
        settings["DOWNLOADER_MIDDLEWARES"]["scrapy_poet.DownloaderStatsMiddleware"] = (
            850
        )
        settings["REQUEST_FINGERPRINTER_CLASS"] = ScrapyPoetRequestFingerprinter
        settings["SPIDER_MIDDLEWARES"] = {
            "scrapy_poet.RetryMiddleware": 275,
        }
    else:
        settings["ADDONS"] = {
            "scrapy_poet.Addon": 300,
        }
    try:
        from scrapy.utils.test import get_reactor_settings  # noqa: PLC0415

        settings.update(get_reactor_settings())
    except ImportError:
        # Scrapy < 2.13.0, no need to change the reactor settings
        pass
    return settings


def create_scrapy_settings() -> Settings:
    """Return the default scrapy-poet settings."""
    warn(
        "The scrapy_poet.utils.create_scrapy_settings() function is deprecated.",
        DeprecationWarning,
        stacklevel=2,
    )
    return Settings(_get_test_settings())


def capture_exceptions(
    callback: Callable[..., Any],
) -> Callable[..., AsyncIterator[Any]]:
    """Wrapper for Scrapy callbacks that captures exceptions within
    the provided callback and yields it under `exception` property. Also
    spider is closed on the first exception."""

    async def parse(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        try:
            if isasyncgenfunction(callback):
                async for x in callback(*args, **kwargs):
                    yield x
            else:
                for x in callback(*args, **kwargs):
                    yield x
        except Exception as e:
            yield {"exception": e}
            raise CloseSpider("Exception in callback detected") from e

    # Mimic type annotations
    parse.__annotations__ = callback.__annotations__
    return parse
