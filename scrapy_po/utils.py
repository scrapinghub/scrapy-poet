# -*- coding: utf-8 -*-
from scrapy.http import Response


def get_callback(request, spider):
    """ Get request.callback of a scrapy.Request, as a callable """
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback


class DummyResponse(Response):

    def __init__(self, url, request=None):
        super(DummyResponse, self).__init__(url=url, request=request)
