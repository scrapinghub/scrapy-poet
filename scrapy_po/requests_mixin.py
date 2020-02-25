# -*- coding: utf-8 -*-
from typing import Type

from scrapy import Request
from urllib.parse import urljoin


class RequestsFromUrlsMixin():
    """ Add a method `requests` that wraps urls returned by method `urls`
    into ``Request``s and yield it so that can be used in a Scrapy callback
    in the form of ``yield from obj.requests(...args...). Note that this
    mixin expects the parent to have the ``urls`` and ``url`` methods defined """

    def requests(self, *args, **kwargs):
        for url in self.urls():
            yield Request(urljoin(self.url, url),
                          *args, **kwargs)


def add_requests_method(class_with_urls_method: Type):
    """ Adds ``RequestsFromUrlsMixin`` capabilities to the class """

    class WithRequestsMethod(class_with_urls_method, RequestsFromUrlsMixin):
        pass

    return WithRequestsMethod
