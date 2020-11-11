import scrapy
import pytest
from scrapy.utils.reqser import request_to_dict

from web_poet.pages import ItemPage, ItemWebPage
from scrapy_poet import (
    callback_for,
    DummyResponse,
)


class FakeItemPage(ItemPage):

    def to_item(self):
        return 'fake item page'


class FakeItemWebPage(ItemWebPage):

    def to_item(self):
        return 'fake item web page'


class MySpider(scrapy.Spider):

    name = 'my_spider'
    parse_item = callback_for(FakeItemPage)
    parse_web = callback_for(FakeItemWebPage)


def test_callback_for():
    """Simple test case to ensure it works as expected."""
    cb = callback_for(FakeItemPage)
    assert callable(cb)

    fake_page = FakeItemPage()
    response = DummyResponse('http://example.com/')
    result = cb(response=response, page=fake_page)
    assert list(result) == ['fake item page']


def test_callback_for_instance_method():
    spider = MySpider()
    response = DummyResponse('http://example.com/')
    fake_page = FakeItemPage()
    result = spider.parse_item(response, page=fake_page)
    assert list(result) == ['fake item page']


def test_callback_for_inline():
    callback = callback_for(FakeItemPage)
    response = DummyResponse('http://example.com/')
    fake_page = FakeItemPage()
    result = callback(response, page=fake_page)
    assert list(result) == ['fake item page']


def test_default_callback():
    """Sample request not specifying callback."""
    spider = MySpider()
    request = scrapy.Request('http://example.com/')
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] is None


def test_instance_method_callback():
    """Sample request specifying spider's instance method callback."""
    spider = MySpider()
    request = scrapy.Request('http://example.com/', callback=spider.parse_item)
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] == 'parse_item'

    request = scrapy.Request('http://example.com/', callback=spider.parse_web)
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] == 'parse_web'


def test_inline_callback():
    """Sample request with inline callback."""
    spider = MySpider()
    cb = callback_for(FakeItemPage)
    request = scrapy.Request('http://example.com/', callback=cb)
    with pytest.raises(ValueError) as exc:
        request_to_dict(request, spider)

    msg = f'Function {cb} is not an instance method in: {spider}'
    assert str(exc.value) == msg


def test_invalid_subclass():
    """Classes should inherit from ItemPage."""

    class MyClass(object):
        pass

    with pytest.raises(TypeError) as exc:
        callback_for(MyClass)

    msg = 'MyClass should be a subclass of ItemPage.'
    assert str(exc.value) == msg


def test_not_implemented_method():
    """Classes should implement to_item method."""

    class MyClass(ItemPage):
        pass

    with pytest.raises(NotImplementedError) as exc:
        callback_for(MyClass)

    msg = 'MyClass should implement to_item method.'
    assert str(exc.value) == msg
