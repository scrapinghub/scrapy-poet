# -*- coding: utf-8 -*-
import abc

from scrapy.http.response import Response
from core_po.page_inputs import ResponseData

# fixme: refactor _providers / provides / register,  make a nicer API
providers = {}


def register(provider, cls):
    """Register a class as providing a certain page object input
    of type ``cls``.
    """
    providers[cls] = provider


def provides(cls):
    def decorator(provider):
        register(provider, cls)
        return provider
    return decorator


class PageObjectInputProvider(abc.ABC):

    @abc.abstractmethod
    def __call__(self):
        pass


@provides(ResponseData)
class ResponseDataProvider(PageObjectInputProvider):

    def __init__(self, response: Response):
        self.response = response

    def __call__(self):
        return ResponseData(
            url=self.response.url,
            html=self.response.text
        )
