import attr
from typing import Any, Dict

import scrapy
from scrapy.http import TextResponse
from scrapy.settings import Settings

from scrapy_poet.page_input_providers import (
    PageObjectInputProvider,
    ResponseDataProvider,
)
from web_poet.pages import ItemPage, WebPage

from scrapy_poet.utils import (
    callback_for,
    get_callback,
    is_callback_using_response,
    is_provider_using_response,
    is_response_going_to_be_used,
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

    def __init__(self, request: scrapy.Request):
        self.request = request

    def __call__(self, provided_classes):
        data = {
            'product': {
                'url': self.request.url,
                'name': 'Sample',
            },
        }
        return {
            DummyProductResponse: DummyProductResponse(data=data)
        }


class FakeProductProvider(PageObjectInputProvider):

    provided_classes = {FakeProductResponse}

    def __call__(self, provided_classes):
        data = {
            'product': {
                'url': 'http://example.com/sample',
                'name': 'Sample',
            },
        }
        return {
            DummyProductResponse: DummyProductResponse(data=data)
        }


class TextProductProvider(ResponseDataProvider):

    # This is wrong. You should not annotate provider dependencies with classes
    # like TextResponse or HtmlResponse, you should use Response instead.
    def __init__(self, response: TextResponse):
        self.response = response


class StringProductProvider(ResponseDataProvider):

    def __init__(self, response: str):
        self.response = response


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
        "SCRAPY_POET_PROVIDERS": [
            ResponseDataProvider,
            DummyProductProvider,
            FakeProductProvider,
        ]
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
    assert is_provider_using_response(PageObjectInputProvider) is False
    assert is_provider_using_response(ResponseDataProvider) is True
    # TextProductProvider wrongly annotates response dependency as
    # TextResponse, instead of using the Response type.
    assert is_provider_using_response(TextProductProvider) is False
    assert is_provider_using_response(DummyProductProvider) is False
    assert is_provider_using_response(FakeProductProvider) is False
    assert is_provider_using_response(StringProductProvider) is False


def test_is_callback_using_response():
    spider = MySpider()
    assert is_callback_using_response(spider.parse) is True
    assert is_callback_using_response(spider.parse2) is True
    assert is_callback_using_response(spider.parse3) is False
    assert is_callback_using_response(spider.parse4) is False
    assert is_callback_using_response(spider.parse5) is True
    assert is_callback_using_response(spider.parse6) is False
    assert is_callback_using_response(spider.parse7) is True
    assert is_callback_using_response(spider.parse8) is False
    assert is_callback_using_response(spider.parse9) is True
    assert is_callback_using_response(spider.parse10) is False
    assert is_callback_using_response(spider.parse11) is True
    assert is_callback_using_response(spider.parse12) is True
    # Callbacks created with the callback_for function won't make use of
    # the response, but their providers might use them.
    assert is_callback_using_response(spider.callback_for_parse) is False


def test_is_response_going_to_be_used():
    spider = MySpider()

    # Spider settings are updated when it's initialized from a Crawler.
    # Since we're manually initializing it, let's just copy custom settings
    # and use them as our settings object.
    spider.settings = Settings(spider.custom_settings)

    request = scrapy.Request("http://example.com")
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse2)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse3)
    assert is_response_going_to_be_used(request, spider) is False

    request = scrapy.Request("http://example.com", callback=spider.parse4)
    assert is_response_going_to_be_used(request, spider) is False

    request = scrapy.Request("http://example.com", callback=spider.parse5)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse6)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse7)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse8)
    assert is_response_going_to_be_used(request, spider) is False

    request = scrapy.Request("http://example.com", callback=spider.parse9)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse10)
    assert is_response_going_to_be_used(request, spider) is False

    request = scrapy.Request("http://example.com", callback=spider.parse11)
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse12)
    assert is_response_going_to_be_used(request, spider) is True
