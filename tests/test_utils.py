# -*- coding: utf-8 -*-
import scrapy
from scrapy_po.utils import get_callback


class MySpider(scrapy.Spider):
    name = 'foo'

    def parse(self, response):
        pass

    def parse2(self, response):
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
