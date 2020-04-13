# -*- coding: utf-8 -*-
import scrapy
from scrapy_po.utils import (
    get_callback,
    is_response_going_to_be_used,
    DummyResponse,
)


class MySpider(scrapy.Spider):
    name = 'foo'

    def parse(self, response):
        pass

    def parse2(self, response):
        pass

    def parse3(self, response: DummyResponse):
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


def test_is_response_going_to_be_used():
    spider = MySpider()

    request = scrapy.Request("http://example.com")
    assert is_response_going_to_be_used(request, spider) is True

    request = scrapy.Request("http://example.com", callback=spider.parse3)
    assert is_response_going_to_be_used(request, spider) is False
