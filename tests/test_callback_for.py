import scrapy
import pytest
from scrapy.utils.reqser import request_to_dict

from scrapy_po.webpage import ItemPage, WebPage
from scrapy_po.utils import (
    callback_for,
    is_response_going_to_be_used,
    DummyResponse,
)


class FakePage(ItemPage):

    def to_item(self):
        return 'it works!'


class MySpider(scrapy.Spider):

    name = 'my_spider'
    parse_item = callback_for(ItemPage)
    parse_web = callback_for(WebPage)


def test_callback_for():
    """Simple test case to ensure it works as expected."""
    cb = callback_for(FakePage)
    assert callable(cb)

    fake_page = FakePage()
    response = DummyResponse('http://example.com/')
    assert list(cb(response=response, page=fake_page)) == ['it works!']


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
    cb = callback_for(FakePage)
    request = scrapy.Request('http://example.com/', callback=cb)
    with pytest.raises(ValueError) as exc:
        request_to_dict(request, spider)

    msg = f'Function {cb} is not a method of: {spider}'
    assert str(exc.value) == msg
