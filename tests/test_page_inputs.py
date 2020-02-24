# -*- coding: utf-8 -*-
from scrapy_po.page_inputs import ResponseData


def test_response_data():
    rd = ResponseData("url", "content")
    assert rd.url == "url"
    assert rd.html == "content"