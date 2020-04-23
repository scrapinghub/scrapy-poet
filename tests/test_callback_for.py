import pytest
import scrapy

from core_po.objects import PageObject, WebPageObject
from scrapy.utils.reqser import request_to_dict

from scrapy_po.utils import (
    DummyResponse,
    callback_for,
    is_response_going_to_be_used,
)


class FakePageObject(PageObject):

    def serialize(self):
        return 'fake item page'


class FakeWebPageObject(WebPageObject):

    def serialize(self):
        return 'fake item web page'


class MySpider(scrapy.Spider):

    name = 'my_spider'
    parse_item = callback_for(FakePageObject)
    parse_web = callback_for(FakeWebPageObject)


def test_callback_for():
    """Simple test case to ensure it works as expected."""
    cb = callback_for(FakePageObject)
    assert callable(cb)

    fake_page = FakePageObject()
    response = DummyResponse('http://example.com/')
    result = cb(response=response, page=fake_page)
    assert list(result) == ['fake item page']


def test_callback_for_instance_method():
    spider = MySpider()
    response = DummyResponse('http://example.com/')
    fake_page = FakePageObject()
    result = spider.parse_item(response, page=fake_page)
    assert list(result) == ['fake item page']


def test_callback_for_inline():
    callback = callback_for(FakePageObject)
    response = DummyResponse('http://example.com/')
    fake_page = FakePageObject()
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
    assert is_response_going_to_be_used(request, spider) is False

    request = scrapy.Request('http://example.com/', callback=spider.parse_web)
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] == 'parse_web'
    assert is_response_going_to_be_used(request, spider) is True


def test_inline_callback():
    """Sample request with inline callback."""
    spider = MySpider()
    cb = callback_for(FakePageObject)
    request = scrapy.Request('http://example.com/', callback=cb)
    with pytest.raises(ValueError) as exc:
        request_to_dict(request, spider)

    msg = f'Function {cb} is not a method of: {spider}'
    assert str(exc.value) == msg


def test_invalid_subclass():
    """Classes should inherit from PageObject."""

    class MyClass(object):
        pass

    with pytest.raises(TypeError) as exc:
        callback_for(MyClass)

    msg = 'MyClass should be a sub-class of PageObject.'
    assert str(exc.value) == msg


def test_not_implemented_method():
    """Classes should implement serialize method."""

    class MyClass(PageObject):
        pass

    with pytest.raises(NotImplementedError) as exc:
        callback_for(MyClass)

    msg = 'MyClass should implement serialize method.'
    assert str(exc.value) == msg
