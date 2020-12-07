import attr
from typing import Any, Dict

from pytest_twisted import inlineCallbacks

import scrapy
from scrapy.crawler import Crawler
from scrapy.http import TextResponse, HtmlResponse
from scrapy.settings import Settings
from scrapy_poet.injection import Injector, get_callback, \
    is_callback_requiring_scrapy_response, is_provider_requiring_scrapy_response

from scrapy_poet.page_input_providers import (
    PageObjectInputProvider,
    ResponseDataProvider,
)
from web_poet import ItemPage, WebPage

from scrapy_poet import (
    callback_for,
    DummyResponse,
)


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
            'product': {
                'url': request.url,
                'name': 'Sample',
            },
        }
        return [DummyProductResponse(data=data)]


class FakeProductProvider(PageObjectInputProvider):

    provided_classes = {FakeProductResponse}

    def __call__(self, to_provide):
        data = {
            'product': {
                'url': 'http://example.com/sample',
                'name': 'Sample',
            },
        }
        return [FakeProductResponse(data=data)]


class TextProductProvider(ResponseDataProvider):

    # This is wrong. You should not annotate provider dependencies with classes
    # like TextResponse or HtmlResponse, you should use Response instead.
    def __call__(self, to_provide, response: TextResponse):
        return super().__call__(to_provide, response)


class StringProductProvider(ResponseDataProvider):

    def __call__(self, to_provide, response: str):
        return super().__call__(to_provide, response)


@attr.s(auto_attribs=True)
class DummyProductPage(ItemPage):

    response: DummyProductResponse

    @property
    def url(self):
        return self.response.data['product']['url']

    def to_item(self):
        product = self.response.data['product']
        return product


@attr.s(auto_attribs=True)
class FakeProductPage(ItemPage):

    response: FakeProductResponse

    @property
    def url(self):
        return self.response.data['product']['url']

    def to_item(self):
        product = self.response.data['product']
        return product


class BookPage(WebPage):

    def to_item(self):
        pass


class MySpider(scrapy.Spider):

    name = 'foo'
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": {
            ResponseDataProvider: 1,
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
    assert is_provider_requiring_scrapy_response(ResponseDataProvider) is True
    # TextProductProvider wrongly annotates response dependency as
    # TextResponse, instead of using the Response type.
    assert is_provider_requiring_scrapy_response(TextProductProvider) is False
    assert is_provider_requiring_scrapy_response(DummyProductProvider) is False
    assert is_provider_requiring_scrapy_response(FakeProductProvider) is False
    assert is_provider_requiring_scrapy_response(StringProductProvider) is False


def test_is_callback_using_response():
    spider = MySpider()
    assert is_callback_requiring_scrapy_response(spider.parse) is True
    assert is_callback_requiring_scrapy_response(spider.parse2) is True
    assert is_callback_requiring_scrapy_response(spider.parse3) is False
    assert is_callback_requiring_scrapy_response(spider.parse4) is False
    assert is_callback_requiring_scrapy_response(spider.parse5) is True
    assert is_callback_requiring_scrapy_response(spider.parse6) is False
    assert is_callback_requiring_scrapy_response(spider.parse7) is True
    assert is_callback_requiring_scrapy_response(spider.parse8) is False
    assert is_callback_requiring_scrapy_response(spider.parse9) is True
    assert is_callback_requiring_scrapy_response(spider.parse10) is False
    assert is_callback_requiring_scrapy_response(spider.parse11) is True
    assert is_callback_requiring_scrapy_response(spider.parse12) is True
    # Callbacks created with the callback_for function won't make use of
    # the response, but their providers might use them.
    assert is_callback_requiring_scrapy_response(spider.callback_for_parse) is False


@inlineCallbacks
def test_is_response_going_to_be_used():
    crawler = Crawler(MySpider)
    spider = MySpider()
    crawler.spider = spider

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
