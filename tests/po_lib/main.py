import attrs
from web_poet import Injectable, ItemPage, WebPage, field, handle_urls, item_from_fields

from . import URL


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
class PriorityParentProduct:
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
class BothToReturnAndInsteadOfProduct:
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


@handle_urls(URL)
class PriorityParentProductPage(ItemPage[PriorityParentProduct]):
    @field
    def name(self) -> str:
        return "priority parent product's name"


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


@handle_urls(URL, to_return=StandaloneProduct)
class StandaloneProductPage(ItemPage):
    @field
    def name(self) -> str:
        return "standalone product's name"


class ReplacedToReturnAndInsteadOfProductPage(ItemPage):
    pass


@handle_urls(URL, instead_of=ReplacedToReturnAndInsteadOfProductPage)
class BothToReturnAndInsteadOfProductPage(ItemPage[BothToReturnAndInsteadOfProduct]):
    @field
    def name(self) -> str:
        return "to_return and instead_of product's name"


@handle_urls(URL, to_return=ProductFromInjectable)
class ProductFromInjectablePage(Injectable):
    @field
    def name(self) -> str:
        return "product from injectable"

    async def to_item(self) -> ProductFromInjectable:
        return await item_from_fields(self, item_cls=ProductFromInjectable)
