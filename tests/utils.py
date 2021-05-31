from typing import Dict

from pytest_twisted import inlineCallbacks
from scrapy.exceptions import CloseSpider
from twisted.web.resource import Resource
from scrapy.crawler import Crawler
from tests.mockserver import MockServer
from scrapy.utils.python import to_bytes


class HtmlResource(Resource):
    isLeaf = True
    content_type = 'text/html'
    html = ''
    extra_headers: Dict[str, str] = {}
    status_code = 200

    def render_GET(self, request):
        request.setHeader(b'content-type', to_bytes(self.content_type))
        for name, value in self.extra_headers.items():
            request.setHeader(to_bytes(name), to_bytes(value))
        request.setResponseCode(self.status_code)
        return to_bytes(self.html)


@inlineCallbacks
def crawl_items(spider_cls, resource_cls, settings, spider_kwargs=None):
    """Use spider_cls to crawl resource_cls. URL of the resource is passed
    to the spider as ``url`` argument.
    Return ``(items, resource_url, crawler)`` tuple.
    """
    spider_kwargs = {} if spider_kwargs is None else spider_kwargs
    crawler = make_crawler(spider_cls, settings)
    with MockServer(resource_cls) as s:
        root_url = s.root_url
        yield crawler.crawl(url=root_url, **spider_kwargs)
    return crawler.spider.collected_items, s.root_url, crawler


@inlineCallbacks
def crawl_single_item(spider_cls, resource_cls, settings, spider_kwargs=None):
    """Run a spider where a single item is expected. Use in combination with
    ``capture_capture_exceptions`` and ``CollectorPipeline``
    """
    items, url, crawler = yield crawl_items(spider_cls, resource_cls, settings,
                                            spider_kwargs=spider_kwargs)
    assert len(items) == 1
    resp = items[0]
    if 'exception' in resp:
        raise resp['exception']
    return resp, url, crawler


def make_crawler(spider_cls, settings):
    if not getattr(spider_cls, 'name', None):
        class Spider(spider_cls):
            name = 'test_spider'
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


def capture_exceptions(callback):
    """ Wrapper for Scrapy callbacks that captures exceptions within
    the provided callback and yields it under `exception` property. Also
    spider is closed on the first exception. """
    def parse(*args, **kwargs):
        try:
            yield from callback(*args, **kwargs)
        except Exception as e:
            yield {'exception': e}
            raise CloseSpider("Exception in callback detected")
    # Mimic type annotations
    parse.__annotations__ = callback.__annotations__
    return parse
