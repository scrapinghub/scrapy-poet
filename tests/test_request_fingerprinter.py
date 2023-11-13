import sys
from unittest.mock import patch

import pytest
from packaging.version import Version
from scrapy import __version__ as SCRAPY_VERSION

if Version(SCRAPY_VERSION) < Version("2.7"):
    pytest.skip("Skipping tests for Scrapy < 2.7", allow_module_level=True)

from importlib.metadata import version as package_version

from scrapy import Request, Spider
from web_poet import ItemPage, WebPage

from scrapy_poet import ScrapyPoetRequestFingerprinter
from scrapy_poet.utils.testing import get_crawler as _get_crawler

ANDI_VERSION = Version(package_version("andi"))

SETTINGS = {
    "DOWNLOADER_MIDDLEWARES": {
        "scrapy_poet.InjectionMiddleware": 543,
    },
    "REQUEST_FINGERPRINTER_CLASS": ScrapyPoetRequestFingerprinter,
}


def get_crawler(spider_cls=None, settings=None):
    settings = SETTINGS if settings is None else settings
    kwargs = {}
    if spider_cls is not None:
        kwargs["spider_cls"] = spider_cls
    return _get_crawler(settings=settings, **kwargs)


def test_no_deps_vs_dep():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_page)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


def test_same_deps():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=crawler.spider.parse_page)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_page)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_same_deps_different_callbacks():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response, a: WebPage):
            pass

        async def parse_b(self, response, b: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=crawler.spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_same_deps_different_order():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response, a: WebPage, b: ItemPage):
            pass

        async def parse_b(self, response, a: ItemPage, b: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=crawler.spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 == fingerprint2


def test_different_deps():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_item(self, response, item: ItemPage):
            pass

        async def parse_web(self, response, web: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=crawler.spider.parse_item)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_web)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="No Annotated support in Python < 3.9"
)
@pytest.mark.skipif(
    ANDI_VERSION <= Version("0.4.1"),
    reason="https://github.com/scrapinghub/andi/pull/25",
)
def test_different_annotations():
    from typing import Annotated

    class TestSpider(Spider):
        name = "test_spider"

        async def parse_a(self, response, a: Annotated[WebPage, "a"]):
            pass

        async def parse_b(self, response, b: Annotated[WebPage, "b"]):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    request1 = Request("https://toscrape.com", callback=crawler.spider.parse_a)
    fingerprint1 = fingerprinter.fingerprint(request1)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_b)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert fingerprint1 != fingerprint2


def test_base_default():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    base_fingerprinter = crawler.request_fingerprinter._base_request_fingerprinter

    request1 = Request("https://toscrape.com")
    fingerprint1 = fingerprinter.fingerprint(request1)
    base_fingerprint = base_fingerprinter.fingerprint(request1)
    assert fingerprint1 == base_fingerprint

    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_page)
    fingerprint2 = fingerprinter.fingerprint(request2)
    assert base_fingerprint == base_fingerprinter.fingerprint(request2)
    assert fingerprint2 != base_fingerprint


def test_base_custom():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    class CustomFingerprinter:
        def fingerprint(self, request):
            return b"foo"

    settings = {
        **SETTINGS,
        "SCRAPY_POET_REQUEST_FINGERPRINTER_BASE_CLASS": CustomFingerprinter,
    }
    crawler = get_crawler(spider_cls=TestSpider, settings=settings)
    fingerprinter = crawler.request_fingerprinter

    request = Request("https://example.com")
    assert fingerprinter.fingerprint(request) == b"foo"
    request = Request("https://example.com", callback=crawler.spider.parse_page)
    assert fingerprinter.fingerprint(request) != b"foo"


def test_missing_middleware():
    settings = {**SETTINGS, "DOWNLOADER_MIDDLEWARES": {}}
    crawler = get_crawler(settings=settings)
    fingerprinter = crawler.request_fingerprinter
    request = Request("https://example.com")
    with pytest.raises(RuntimeError):
        fingerprinter.fingerprint(request)


def test_callback_cache():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    to_wrap = fingerprinter._get_deps
    request1 = Request("https://example.com", callback=crawler.spider.parse_page)
    request2 = Request("https://toscrape.com", callback=crawler.spider.parse_page)
    with patch.object(fingerprinter, "_get_deps", wraps=to_wrap) as mock:
        fingerprinter.fingerprint(request1)
        fingerprinter.fingerprint(request2)
        mock.assert_called_once_with(request1)


def test_request_cache():
    class TestSpider(Spider):
        name = "test_spider"

        async def parse_page(self, response, page: WebPage):
            pass

    crawler = get_crawler(spider_cls=TestSpider)
    fingerprinter = crawler.request_fingerprinter
    base_fingerprinter = fingerprinter._base_request_fingerprinter
    to_wrap = base_fingerprinter.fingerprint
    request = Request("https://example.com", callback=crawler.spider.parse_page)
    with patch.object(base_fingerprinter, "fingerprint", wraps=to_wrap) as mock:
        fingerprinter.fingerprint(request)
        fingerprinter.fingerprint(request)
        mock.assert_called_once_with(request)
