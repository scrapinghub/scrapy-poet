import scrapy
import pytest
from scrapy.utils.reqser import request_to_dict

from scrapy_po.webpage import callback_for, ItemPage


class FakePage(ItemPage):

    def to_item(self):
        return 'it works!'


class MySpider(scrapy.Spider):
    name = 'my_spider'
    parse = callback_for(FakePage)


def test_callback_for():
    """Simple test case to ensure it works as expected."""
    cb = callback_for(FakePage)
    assert callable(cb)

    fake_page = FakePage()
    assert list(cb(page=fake_page)) == ['it works!']


def test_callback_serialization():
    """Make sure callbacks are serializable."""
    spider = MySpider()

    # Sample request without callback (fallback to default spider.parse)
    request = scrapy.Request('http://example.com/')
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] is None

    # Sample request referencing callback on spider
    request = scrapy.Request('http://example.com/', callback=spider.parse)
    request_dict = request_to_dict(request, spider)
    assert isinstance(request_dict, dict)
    assert request_dict['url'] == 'http://example.com/'
    assert request_dict['callback'] == 'parse'

    # Sample request referencing callback outside spider
    cb = callback_for(FakePage)
    request = scrapy.Request('http://example.com/', callback=cb)
    with pytest.raises(ValueError) as exc:
        request_to_dict(request, spider)

    msg = f'Function {cb} is not a method of: {spider}'
    assert str(exc.value) == msg
