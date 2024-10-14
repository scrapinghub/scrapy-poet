"""
Example of how to create a PageObject with a very different input data,
which even requires an API request.
"""

from typing import Any, Dict

import attr
from scrapy import Request
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread
from web_poet import ItemPage

from scrapy_poet.page_input_providers import PageObjectInputProvider


@attr.s(auto_attribs=True)
class AutoextractProductResponse:
    """Input data"""

    data: Dict[str, Any]


class AutoextractProductProvider(PageObjectInputProvider):
    provided_classes = {AutoextractProductResponse}

    @inlineCallbacks
    def __call__(self, to_provide, request: Request):
        data = yield get_autoextract_product(request.url)
        return [AutoextractProductResponse(data=data)]


@inlineCallbacks
def get_autoextract_product(url):
    # fixme: use async
    # fixme: rate limits?
    from autoextract.sync import request_batch

    resp = yield deferToThread(request_batch, urls=[url], page_type="product")
    return resp[0]


@attr.s(auto_attribs=True)
class ProductPage(ItemPage):
    """Generic product page"""

    autoextract_resp: AutoextractProductResponse

    @property
    def url(self):
        return self.autoextract_resp.data["product"]["url"]

    def to_item(self):
        product = self.autoextract_resp.data["product"]
        return product
