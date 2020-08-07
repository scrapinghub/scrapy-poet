"""
Example of how to create a PageObject with a very different input data,
which even requires an API request.
"""
from typing import Dict, Any

import attr
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads import deferToThread

from scrapy_poet.repository import provider
from scrapy_poet.providers import PageObjectInputProvider
from web_poet.pages import ItemPage
from scrapy_poet.utils import DummyResponse


@attr.s(auto_attribs=True)
class AutoextractProductResponse:
    """ Input data """
    data: Dict[str, Any]


@provider
class AutoextractProductProvider(PageObjectInputProvider):

    provided_class = AutoextractProductResponse

    def __init__(self, response: DummyResponse):
        self.response = response

    @inlineCallbacks
    def __call__(self):
        data = (yield get_autoextract_product(self.response.url))
        res = AutoextractProductResponse(data=data)
        raise returnValue(res)


@inlineCallbacks
def get_autoextract_product(url):
    # fixme: use async
    # fixme: rate limits?
    from autoextract.sync import request_batch
    resp = yield deferToThread(request_batch, urls=[url], page_type='product')
    raise returnValue(resp[0])


@attr.s(auto_attribs=True)
class ProductPage(ItemPage):
    """ Generic product page """
    autoextract_resp: AutoextractProductResponse

    @property
    def url(self):
        return self.autoextract_resp.data['product']['url']

    def to_item(self):
        product = self.autoextract_resp.data['product']
        return product
