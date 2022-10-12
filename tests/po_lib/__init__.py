"""
This package is just for overrides testing purposes.
"""
import socket

import attrs
from url_matcher.util import get_domain
from web_poet import Injectable, ItemPage, WebPage, field, handle_urls, item_from_fields

from tests.mockserver import get_ephemeral_port

# Need to define it here since it's always changing
DOMAIN = get_domain(socket.gethostbyname(socket.gethostname()))
PORT = get_ephemeral_port()
URL = f"{DOMAIN}:{PORT}"


class POOverridenPage(WebPage):
    def to_item(self):
        return {"msg": "PO that will be replaced"}


@handle_urls(URL, instead_of=POOverridenPage)
class POIntegrationPage(WebPage):
    def to_item(self):
        return {"msg": "PO replacement"}


@attrs.define
class Product:
    name: str


@attrs.define
class ParentProduct:
    name: str


@attrs.define
class ReplacedProduct:
    name: str


@attrs.define
class ParentReplacedProduct:
    name: str


@attrs.define
class SubclassReplacedProduct:
    name: str


@attrs.define
class StandaloneProduct:
    name: str


@attrs.define
class ProductFromInjectable:
    name: str


@handle_urls(URL)
class ProductPage(ItemPage[Product]):
    @field
    def name(self) -> str:
        return "product's name"


@handle_urls(URL)
class ParentProductPage(ItemPage[ParentProduct]):
    @field
    def name(self) -> str:
        return "parent product's name"


@handle_urls(URL, priority=600)
class SubclassProductPage(ParentProductPage):
    @field
    def name(self) -> str:
        return "subclass product's name"


@handle_urls(URL, to_return=ReplacedProduct)
class ReplacedProductPage(ItemPage[Product]):
    @field
    def name(self) -> str:
        return "replaced product's name"


@handle_urls(URL)
class ParentReplacedProductPage(ItemPage[ParentReplacedProduct]):
    @field
    def name(self) -> str:
        return "parent replaced product's name"


@handle_urls(URL, to_return=SubclassReplacedProduct)
class SubclassReplacedProductPage(ParentReplacedProductPage):
    @field
    def name(self) -> str:
        return "subclass replaced product's name"


@handle_urls(URL, to_return=StandaloneProduct)
class StandaloneProductPage(ItemPage):
    @field
    def name(self) -> str:
        return "standalone product's name"


# TODO: cases where `instead_of` and `to_return` are present, including
# permutations of the cases above


@handle_urls(URL, to_return=ProductFromInjectable)
class ProductFromInjectablePage(Injectable):
    @field
    def name(self) -> str:
        return "product from injectable"

    async def to_item(self) -> ProductFromInjectable:
        return await item_from_fields(self, item_cls=ProductFromInjectable)
