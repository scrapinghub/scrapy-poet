from web_poet import field, handle_urls

from . import URL
from .main import (
    ParentProductPage,
    ParentReplacedProductPage,
    PriorityParentProductPage,
    SubclassReplacedProduct,
)


@handle_urls(URL)
class SubclassProductPage(ParentProductPage):
    @field
    def name(self) -> str:
        return "subclass product's name"


@handle_urls(URL, to_return=SubclassReplacedProduct)
class SubclassReplacedProductPage(ParentReplacedProductPage):
    @field
    def name(self) -> str:
        return "subclass replaced product's name"


@handle_urls(URL, priority=600)
class PrioritySubclassProductPage(PriorityParentProductPage):
    @field
    def name(self) -> str:
        return "priority subclass product's name"
