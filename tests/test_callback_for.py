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

class FakeItemPageAsync(ItemPage):

    async def to_item(self):
        return 'fake item page'


class FakeItemWebPage(ItemWebPage):

    def to_item(self):
        return 'fake item web page'


class MySpider(scrapy.Spider):

    name = 'my_spider'
    parse_item = callback_for(FakeItemPage)
    parse_web = callback_for(FakeItemWebPage)


class MySpiderAsync(scrapy.Spider):

    name = 'my_spider_async'
    parse_item = callback_for(FakeItemPageAsync, is_async=True)


def test_callback_for():
    """Simple test case to ensure it works as expected."""
    cb = callback_for(FakeItemPage)
    assert callable(cb)

    fake_page = FakeItemPage()
    response = DummyResponse('http://example.com/')
    result = cb(response=response, page=fake_page)
    assert list(result) == ['fake item page']


@pytest.mark.asyncio
async def test_callback_for_async():
    cb = callback_for(FakeItemPage, is_async=True)
    assert callable(cb)

    fake_page = FakeItemPageAsync()
    response = DummyResponse('http://example.com/')
    result = cb(response=response, page=fake_page)

    assert await result.__anext__() == 'fake item page'
    with pytest.raises(StopAsyncIteration):
        assert await result.__anext__()


def test_callback_for_instance_method():
    spider = MySpider()
    response = DummyResponse('http://example.com/')
    fake_page = FakeItemPage()
    result = spider.parse_item(response, page=fake_page)
    assert list(result) == ['fake item page']


@pytest.mark.asyncio
async def test_callback_for_instance_method_async():
    spider = MySpiderAsync()
    response = DummyResponse('http://example.com/')
    fake_page = FakeItemPageAsync()
    result = spider.parse_item(response, page=fake_page)

    assert await result.__anext__() == 'fake item page'
    with pytest.raises(StopAsyncIteration):
        assert await result.__anext__()


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


def test_inline_callback_async():
    """Sample request with inline callback using async callback_for."""
    spider = MySpiderAsync()
    cb = callback_for(FakeItemPage, is_async=True)
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
