import warnings
from typing import Any, Dict

import attr
import pytest
import scrapy
from pytest_twisted import inlineCallbacks
from scrapy.crawler import Crawler
from scrapy.http import HtmlResponse, Request, TextResponse
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector
from web_poet import ItemPage, WebPage

from scrapy_poet import DummyResponse, callback_for
from scrapy_poet.injection import (
    Injector,
    get_callback,
    is_callback_requiring_scrapy_response,
    is_provider_requiring_scrapy_response,
)
from scrapy_poet.page_input_providers import (
    HttpResponseProvider,
    PageObjectInputProvider,
)
from scrapy_poet.utils import is_min_scrapy_version

# See: https://github.com/scrapinghub/scrapy-poet/issues/118
try:
    from scrapy.http.request import NO_CALLBACK  # available on Scrapy >= 2.8
except ImportError:
    NO_CALLBACK = lambda: None  # noqa: E731


@attr.s(auto_attribs=True)
class DummyProductResponse:
    data: Dict[str, Any]


@attr.s(auto_attribs=True)
class FakeProductResponse:
    data: Dict[str, Any]


class DummyProductProvider(PageObjectInputProvider):
    provided_classes = {DummyProductResponse}

    def __call__(self, to_provide, request: scrapy.Request):
        data = {
            "product": {
                "url": request.url,
                "name": "Sample",
            },
        }
        return [DummyProductResponse(data=data)]


class FakeProductProvider(PageObjectInputProvider):
    provided_classes = {FakeProductResponse}

    def __call__(self, to_provide):
        data = {
            "product": {
                "url": "http://example.com/sample",
                "name": "Sample",
            },
        }
        return [FakeProductResponse(data=data)]


class TextProductProvider(HttpResponseProvider):
    # This is wrong. You should not annotate provider dependencies with classes
    # like TextResponse or HtmlResponse, you should use Response instead.
    def __call__(self, to_provide, response: TextResponse):
        return super().__call__(to_provide, response)


class StringProductProvider(HttpResponseProvider):
    def __call__(self, to_provide, response: str):
        return super().__call__(to_provide, response)


@attr.s(auto_attribs=True)
class DummyProductPage(ItemPage):
    response: DummyProductResponse

    @property
    def url(self):
        return self.response.data["product"]["url"]

    def to_item(self):
        product = self.response.data["product"]
        return product


@attr.s(auto_attribs=True)
class FakeProductPage(ItemPage):
    response: FakeProductResponse

    @property
    def url(self):
        return self.response.data["product"]["url"]

    def to_item(self):
        product = self.response.data["product"]
        return product


class BookPage(WebPage):
    def to_item(self):
        pass


class MySpider(scrapy.Spider):
    name = "foo"
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            HttpResponseProvider: 1,
            DummyProductProvider: 2,
            FakeProductProvider: 3,
        }
    }
    callback_for_parse = callback_for(DummyProductPage)

    def parse(self, response):
        pass

    def parse2(self, res):
        pass

    def parse3(self, response: DummyResponse):
        pass

    def parse4(self, res: DummyResponse):
        pass

    def parse5(self, response, book_page: BookPage):
        pass

    def parse6(self, response: DummyResponse, book_page: BookPage):
        pass

    def parse7(self, response, book_page: DummyProductPage):
        pass

    def parse8(self, response: DummyResponse, book_page: DummyProductPage):
        pass

    def parse9(self, response, book_page: FakeProductPage):
        pass

    def parse10(self, response: DummyResponse, book_page: FakeProductPage):
        pass

    def parse11(self, response: TextResponse):
        pass

    def parse12(self, response: TextResponse, book_page: DummyProductPage):
        pass


def test_get_callback():
    spider = MySpider()

    req = scrapy.Request("http://example.com")
    assert get_callback(req, spider) == spider.parse

    req = scrapy.Request("http://example.com", spider.parse2)
    assert get_callback(req, spider) == spider.parse2

    def cb(response):
        pass

    req = scrapy.Request("http://example.com", cb)
    assert get_callback(req, spider) == cb


def test_is_provider_using_response():
    assert is_provider_requiring_scrapy_response(PageObjectInputProvider) is False
    assert is_provider_requiring_scrapy_response(HttpResponseProvider) is True
    # TextProductProvider wrongly annotates response dependency as
    # TextResponse, instead of using the Response type.
    assert is_provider_requiring_scrapy_response(TextProductProvider) is False
    assert is_provider_requiring_scrapy_response(DummyProductProvider) is False
    assert is_provider_requiring_scrapy_response(FakeProductProvider) is False
    assert is_provider_requiring_scrapy_response(StringProductProvider) is False


@pytest.mark.skipif(
    is_min_scrapy_version("2.8.0"),
    reason="tests Scrapy < 2.8 before NO_CALLBACK was introduced",
)
def test_is_callback_using_response_for_scrapy28_below() -> None:
    spider = MySpider()
    request = Request("https://example.com", callback=lambda _: _)
    assert is_callback_requiring_scrapy_response(spider.parse, request.callback) is True
    assert (
        is_callback_requiring_scrapy_response(spider.parse2, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse3, request.callback) is False
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse4, request.callback) is False
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse5, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse6, request.callback) is False
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse7, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse8, request.callback) is False
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse9, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse10, request.callback) is False
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse11, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse12, request.callback) is True
    )
    # Callbacks created with the callback_for function won't make use of
    # the response, but their providers might use them.
    assert (
        is_callback_requiring_scrapy_response(spider.callback_for_parse, request)
        is False
    )

    # See: https://github.com/scrapinghub/scrapy-poet/issues/48
    request.callback = None
    expected_warning = (
        "A request has been encountered with callback=None which "
        "defaults to the parse() method. If the parse() method is "
        "annotated with scrapy_poet.DummyResponse (or its subclasses), "
        "we're assuming this isn't intended and would simply ignore "
        "this annotation.\n\n"
        "See the Pitfalls doc for more info."
    )

    assert is_callback_requiring_scrapy_response(spider.parse, request.callback) is True
    assert (
        is_callback_requiring_scrapy_response(spider.parse2, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse5, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse7, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse9, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse11, request.callback) is True
    )
    assert (
        is_callback_requiring_scrapy_response(spider.parse12, request.callback) is True
    )

    for method in (
        spider.parse3,
        spider.parse4,
        spider.parse6,
        spider.parse8,
        spider.parse10,
    ):
        with pytest.warns(UserWarning) as record:
            assert (
                is_callback_requiring_scrapy_response(method, request.callback) is True  # type: ignore[arg-type]
            )
            assert expected_warning in str(record.list[0].message)


@pytest.mark.skipif(
    not is_min_scrapy_version("2.8.0"),
    reason="NO_CALLBACK not available in Scrapy < 2.8",
)
def test_is_callback_using_response_for_scrapy28_and_above() -> None:
    spider = MySpider()
    request_with_callback = Request("https://example.com", callback=lambda _: _)
    request_no_callback = Request("https://example.com", callback=NO_CALLBACK)

    with warnings.catch_warnings(record=True) as caught_warnings:
        for request in [request_with_callback, request_no_callback]:
            assert (
                is_callback_requiring_scrapy_response(spider.parse, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse2, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse3, request.callback)
                is False
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse4, request.callback)
                is False
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse5, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse6, request.callback)
                is False
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse7, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse8, request.callback)
                is False
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse9, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse10, request.callback)
                is False
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse11, request.callback)
                is True
            )
            assert (
                is_callback_requiring_scrapy_response(spider.parse12, request.callback)
                is True
            )
            # Callbacks created with the callback_for function won't make use of
            # the response, but their providers might use them.
            assert (
                is_callback_requiring_scrapy_response(
                    spider.callback_for_parse, request
                )
                is False
            )
    assert not caught_warnings


@inlineCallbacks
def test_is_response_going_to_be_used():
    crawler = Crawler(MySpider)
    spider = MySpider()
    crawler.spider = spider
    crawler.stats = MemoryStatsCollector(crawler)

    def response(request):
        return HtmlResponse(request.url, request=request, body=b"<html></html>")

    # Spider settings are updated when it's initialized from a Crawler.
    # Since we're manually initializing it, let's just copy custom settings
    # and use them as our settings object.
    spider.settings = Settings(spider.custom_settings)
    injector = Injector(crawler)

    @inlineCallbacks
    def check_response_required(expected, callback):
        request = scrapy.Request("http://example.com", callback=callback)
        assert injector.is_scrapy_response_required(request) is expected
        yield injector.build_callback_dependencies(request, response(request))

    yield from check_response_required(True, None)
    yield from check_response_required(True, spider.parse2)
    yield from check_response_required(False, spider.parse3)
    yield from check_response_required(False, spider.parse4)
    yield from check_response_required(True, spider.parse5)
    yield from check_response_required(True, spider.parse6)
    yield from check_response_required(True, spider.parse7)
    yield from check_response_required(False, spider.parse8)
    yield from check_response_required(True, spider.parse9)
    yield from check_response_required(False, spider.parse10)
    yield from check_response_required(True, spider.parse11)
    yield from check_response_required(True, spider.parse12)
