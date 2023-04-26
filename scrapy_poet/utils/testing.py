import json
from inspect import isasyncgenfunction
from typing import Dict
from unittest import mock

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import CloseSpider
from scrapy.settings import Settings
from scrapy.utils.python import to_bytes
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from scrapy_poet.utils.mockserver import MockServer


class HtmlResource(Resource):
    isLeaf = True
    content_type = "text/html"
    html = ""
    extra_headers: Dict[str, str] = {}
    status_code = 200

    def render_GET(self, request):
        request.setHeader(b"content-type", to_bytes(self.content_type))
        for name, value in self.extra_headers.items():
            request.setHeader(to_bytes(name), to_bytes(value))
        request.setResponseCode(self.status_code)
        return to_bytes(self.html)


class LeafResource(Resource):
    isLeaf = True

    def deferRequest(self, request, delay, f, *a, **kw):
        def _cancelrequest(_):
            # silence CancelledError
            d.addErrback(lambda _: None)
            d.cancel()

        d = deferLater(reactor, delay, f, *a, **kw)
        request.notifyFinish().addErrback(_cancelrequest)
        return d


class DelayedResource(LeafResource):
    def render_GET(self, request):
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

    def _delayedRender(self, request, seconds):
        request.finish()


class EchoResource(LeafResource):
    def render_GET(self, request):
        return request.content.read()


class HeadersResource(LeafResource):
    def render_GET(self, request):
        return json.dumps(
            {
                k.decode(): [v.decode() for v in vs]
                for k, vs in request.requestHeaders.getAllRawHeaders()
            }
        ).encode()


class StatusResource(LeafResource):
    def render_GET(self, request):
        decoded_body = request.content.read().decode()
        if decoded_body:
            request.setResponseCode(int(decoded_body))
        return b""


class ForbiddenResource(LeafResource):
    def render_GET(self, request):
        request.setResponseCode(403)
        return b""


class DropResource(LeafResource):
    def render_GET(self, request):
        request.setHeader(b"Content-Length", b"10")
        try:
            request.channel.transport.loseConnection()
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
def crawl_items(spider_cls, resource_cls, settings, spider_kwargs=None, port=None):
    """Use spider_cls to crawl resource_cls. URL of the resource is passed
    to the spider as ``url`` argument.
    Return ``(items, resource_url, crawler)`` tuple.
    """
    spider_kwargs = {} if spider_kwargs is None else spider_kwargs
    crawler = make_crawler(spider_cls, settings)
    with MockServer(resource_cls, port=port) as s:
        root_url = s.root_url
        yield crawler.crawl(url=root_url, **spider_kwargs)
    return crawler.spider.collected_items, s.root_url, crawler


@inlineCallbacks
def crawl_single_item(
    spider_cls, resource_cls, settings, spider_kwargs=None, port=None
):
    """Run a spider where a single item is expected. Use in combination with
    ``capture_exceptions`` and ``CollectorPipeline``
    """
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


def make_crawler(spider_cls, settings):
    if not getattr(spider_cls, "name", None):

        class Spider(spider_cls):
            name = "test_spider"

        Spider.__name__ = spider_cls.__name__
        Spider.__module__ = spider_cls.__module__
        spider_cls = Spider
    return Crawler(spider_cls, settings)


class CollectorPipeline:
    def open_spider(self, spider):
        spider.collected_items = []

    def process_item(self, item, spider):
        spider.collected_items.append(item)
        return item


class InjectedDependenciesCollectorMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        return obj

    def spider_opened(self, spider):
        spider.collected_response_deps = []

    def process_response(self, request, response, spider):
        spider.collected_response_deps.append(request.cb_kwargs)
        return response


def create_scrapy_settings(request):
    """Default scrapy-poet settings"""
    s = dict(
        # collect scraped items to crawler.spider.collected_items
        ITEM_PIPELINES={
            CollectorPipeline: 100,
        },
        DOWNLOADER_MIDDLEWARES={
            # collect injected dependencies to crawler.spider.collected_response_deps
            InjectedDependenciesCollectorMiddleware: 542,
            "scrapy_poet.InjectionMiddleware": 543,
        },
    )
    return Settings(s)


def capture_exceptions(callback):
    """Wrapper for Scrapy callbacks that captures exceptions within
    the provided callback and yields it under `exception` property. Also
    spider is closed on the first exception."""

    async def parse(*args, **kwargs):
        try:
            if isasyncgenfunction(callback):
                async for x in callback(*args, **kwargs):
                    yield x
            else:
                for x in callback(*args, **kwargs):
                    yield x
        except Exception as e:
            yield {"exception": e}
            raise CloseSpider("Exception in callback detected")

    # Mimic type annotations
    parse.__annotations__ = callback.__annotations__
    return parse


class AsyncMock(mock.MagicMock):
    """workaround since python 3.7 doesn't ship with asyncmock."""

    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
