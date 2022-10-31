"""This tests scrapy-poet's integration with web-poet's ``ApplyRule`` specifically
when used for callback dependencies.

Most of the logic here tests the behavior of the ``scrapy_poet/injection.py``
module.
"""

import socket
from typing import Any, Type

import attrs
import pytest
import scrapy
from pytest_twisted import inlineCallbacks
from url_matcher import Patterns
from url_matcher.util import get_domain
from web_poet import (
    ApplyRule,
    Injectable,
    ItemPage,
    WebPage,
    default_registry,
    field,
    handle_urls,
    item_from_fields,
)

from scrapy_poet import callback_for
from scrapy_poet.downloadermiddlewares import DEFAULT_PROVIDERS
from tests.mockserver import get_ephemeral_port
from tests.test_middleware import ProductHtml
from tests.utils import capture_exceptions, crawl_single_item, create_scrapy_settings

DOMAIN = get_domain(socket.gethostbyname(socket.gethostname()))
PORT = get_ephemeral_port()
URL = f"{DOMAIN}:{PORT}"


def rules_settings() -> dict:
    settings = create_scrapy_settings(None)
    settings["SCRAPY_POET_OVERRIDES"] = default_registry.get_rules()
    return settings


def spider_for(injectable: Type):
    class InjectableSpider(scrapy.Spider):

        url = None
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": DEFAULT_PROVIDERS,
        }

        def start_requests(self):
            yield scrapy.Request(self.url, capture_exceptions(callback_for(injectable)))

    return InjectableSpider


# TODO: rename this
@inlineCallbacks
def crawl_item_and_deps(PageObject) -> Any:
    """Helper function to easily return the item and injected dependencies from
    a simulated Scrapy callback which asks for either of these dependencies:
        - Page Object
        - Item Type
    """
    item, _, crawler = yield crawl_single_item(
        spider_for(PageObject), ProductHtml, rules_settings(), port=PORT
    )
    return item, crawler.spider.collected_response_deps


def assert_deps(deps, expected):
    """Helper for easily checking the instances of the ``deps`` returned by
    ``crawl_item_and_deps()``.
    """
    assert len(deps) == 1
    assert not deps[0].keys() - expected.keys()
    assert all([True for k, v in expected.items() if isinstance(deps[0][k], v)])


class OverriddenPage(WebPage):
    def to_item(self) -> dict:
        return {"msg": "PO that will be replaced"}


@handle_urls(URL, instead_of=OverriddenPage)
class ReplacementPage(WebPage):
    def to_item(self) -> dict:
        return {"msg": "PO replacement"}


@inlineCallbacks
def test_basic_overrides() -> None:
    """Basic overrides use case.

    If a Page Object is asked for and it's available in a rule's ``instead_of``
    parameter, it would be replaced by the Page Object inside the rule's ``use``
    parameter.
    """
    item, deps = yield crawl_item_and_deps(OverriddenPage)
    assert item == {"msg": "PO replacement"}
    assert_deps(deps, {"page": ReplacementPage})

    # Calling the replacement should also still work
    item, deps = yield crawl_item_and_deps(ReplacementPage)
    assert item == {"msg": "PO replacement"}
    assert_deps(deps, {"page": ReplacementPage})


@attrs.define
class Product:
    name: str


@handle_urls(URL)
class ProductPage(ItemPage[Product]):
    @field
    def name(self) -> str:
        return "product name"


@inlineCallbacks
def test_basic_item_return() -> None:
    """Basic item use case.

    If an item class is asked for and it's available in a rule's ``to_return``
    parameter, an item class's instance shall be produced by the Page Object
    declared inside the rule's ``use`` parameter.
    """
    item, deps = yield crawl_item_and_deps(Product)
    assert item == Product(name="product name")
    assert_deps(deps, {"item": Product})

    # calling the actual Page Object should also work
    item, deps = yield crawl_item_and_deps(ProductPage)
    assert item == Product(name="product name")
    assert_deps(deps, {"page": ProductPage})


@attrs.define
class ProductFromParent:
    name: str


@handle_urls(URL)
class ParentProductPage(ItemPage[ProductFromParent]):
    @field
    def name(self) -> str:
        return "parent product name"


@handle_urls(URL)
class SubclassProductPage(ParentProductPage):
    @field
    def name(self) -> str:
        return "subclass product name"


@inlineCallbacks
def test_item_return_subclass() -> None:
    """A Page Object should properly derive the ``Return[ItemType]`` that it
    inherited from its parent.

    In this test case, there's a clash for the ``url_matcher.Patterns`` since
    they're exactly the same. This produces a warning message. For conflicts
    like this, scrapy-poet follows the latest ``ApplyRule``.

    To remove this warning, the user should update the priority in
    ``url_matcher.Patterns``.
    """
    with pytest.warns(UserWarning, match="Consider explicitly updating the priority"):
        item, deps = yield crawl_item_and_deps(ProductFromParent)
    assert item == ProductFromParent(name="subclass product name")
    assert_deps(deps, {"item": ProductFromParent})

    # calling the actual Page Objects should still work

    item, deps = yield crawl_item_and_deps(ParentProductPage)
    assert item == ProductFromParent(name="parent product name")
    assert_deps(deps, {"page": ParentProductPage})

    item, deps = yield crawl_item_and_deps(SubclassProductPage)
    assert item == ProductFromParent(name="subclass product name")
    assert_deps(deps, {"page": SubclassProductPage})


@attrs.define
class PriorityProductFromParent:
    name: str


@handle_urls(URL, priority=600)
class PriorityParentProductPage(ItemPage[PriorityProductFromParent]):
    @field
    def name(self) -> str:
        return "priority parent product name"


@handle_urls(URL)
class PrioritySubclassProductPage(PriorityParentProductPage):
    @field
    def name(self) -> str:
        return "priority subclass product name"


@inlineCallbacks
def test_item_return_subclass_priority() -> None:
    """Same case as with ``test_item_return_subclass()`` but now the parent PO
    uses a higher priority of 600 than the default 500.
    """
    item, deps = yield crawl_item_and_deps(PriorityProductFromParent)
    assert item == PriorityProductFromParent(name="priority parent product name")
    assert_deps(deps, {"item": PriorityProductFromParent})

    # calling the actual Page Objects should still work

    item, deps = yield crawl_item_and_deps(PriorityParentProductPage)
    assert item == PriorityProductFromParent(name="priority parent product name")
    assert_deps(deps, {"page": PriorityParentProductPage})

    item, deps = yield crawl_item_and_deps(PrioritySubclassProductPage)
    assert item == PriorityProductFromParent(name="priority subclass product name")
    assert_deps(deps, {"page": PriorityParentProductPage})


@attrs.define
class ReplacedProduct:
    name: str


@handle_urls(URL, to_return=ReplacedProduct)
class ReplacedProductPage(ItemPage[Product]):
    @field
    def name(self) -> str:
        return "replaced product name"


@inlineCallbacks
def test_item_to_return_in_handle_urls() -> None:
    """Even if ``@handle_urls`` could derive the value for the ``to_return``
    parameter when the class inherits from something like ``ItemPage[ItemType]``,
    any value passed through its ``to_return`` parameter should take precedence.

    Note that that this produces some inconsistencies between the rule's item
    class vs the class that is actually returned.

    Using the ``to_return`` parameter in ``@handle_urls`` isn't recommended
    because of this.
    """
    item, deps = yield crawl_item_and_deps(ReplacedProduct)
    assert item == Product(name="replaced product name")
    assert_deps(deps, {"item": Product})

    # Requesting the underlying item type from the PO should still work.
    item, deps = yield crawl_item_and_deps(Product)
    assert item == Product(name="product name")
    assert_deps(deps, {"item": Product})

    # calling the actual Page Objects should still work
    item, deps = yield crawl_item_and_deps(ReplacedProductPage)
    assert item == Product(name="replaced product name")
    assert_deps(deps, {"page": ReplacedProductPage})


@attrs.define
class ParentReplacedProduct:
    name: str


@attrs.define
class SubclassReplacedProduct:
    name: str


@handle_urls(URL)
class ParentReplacedProductPage(ItemPage[ParentReplacedProduct]):
    @field
    def name(self) -> str:
        return "parent replaced product name"


@handle_urls(URL, to_return=SubclassReplacedProduct)
class SubclassReplacedProductPage(ParentReplacedProductPage):
    @field
    def name(self) -> str:
        return "subclass replaced product name"


@inlineCallbacks
def test_item_to_return_in_handle_urls_subclass() -> None:
    """Same case as with the ``test_item_to_return_in_handle_urls()`` case above
    but the ``to_return`` is declared in the subclass.
    """
    item, deps = yield crawl_item_and_deps(SubclassReplacedProduct)
    assert item == ParentReplacedProduct(name="subclass replaced product name")
    assert_deps(deps, {"item": ParentReplacedProduct})

    # Requesting the underlying item type from the parent PO should still work.
    item, deps = yield crawl_item_and_deps(ParentReplacedProduct)
    assert item == ParentReplacedProduct(name="parent replaced product name")
    assert_deps(deps, {"item": ParentReplacedProduct})

    # calling the actual Page Objects should still work

    item, deps = yield crawl_item_and_deps(ParentReplacedProductPage)
    assert item == ParentReplacedProduct(name="parent replaced product name")
    assert_deps(deps, {"page": ParentReplacedProductPage})

    item, deps = yield crawl_item_and_deps(SubclassReplacedProductPage)
    assert item == ParentReplacedProduct(name="subclass replaced product name")
    assert_deps(deps, {"page": SubclassReplacedProductPage})


@attrs.define
class StandaloneProduct:
    name: str


@handle_urls(URL, to_return=StandaloneProduct)
class StandaloneProductPage(ItemPage):
    @field
    def name(self) -> str:
        return "standalone product name"


@inlineCallbacks
def test_item_to_return_standalone() -> None:
    """Same case as with ``test_item_to_return_in_handle_urls()`` above but the
    Page Object doesn't inherit from somethine like ``ItemPage[ItemClass]``
    """
    item, deps = yield crawl_item_and_deps(StandaloneProduct)
    assert item == {"name": "standalone product name"}
    assert_deps(deps, {"item": dict})

    # calling the actual Page Object should still work
    item, deps = yield crawl_item_and_deps(StandaloneProductPage)
    assert item == {"name": "standalone product name"}
    assert_deps(deps, {"page": StandaloneProductPage})


@attrs.define
class BiProduct:
    name: str


class ReplacedBiProductPage(ItemPage):
    pass


@handle_urls(URL, instead_of=ReplacedBiProductPage)
class BiProductPage(ItemPage[BiProduct]):
    @field
    def name(self) -> str:
        return "to_return and instead_of product name"


@inlineCallbacks
def test_both_to_return_and_instead_of() -> None:
    """Rules that contain both ``to_return`` and ``instead_of`` should work on
    both cases when either are requested.
    """
    # item from 'to_return'
    item, deps = yield crawl_item_and_deps(BiProduct)
    assert item == BiProduct(name="to_return and instead_of product name")
    assert_deps(deps, {"item": BiProduct})

    # page from 'instead_of'
    item, deps = yield crawl_item_and_deps(ReplacedBiProductPage)
    assert item == BiProduct(name="to_return and instead_of product name")
    assert_deps(deps, {"page": BiProductPage})

    # calling the actual Page Object should still work
    item, deps = yield crawl_item_and_deps(BiProductPage)
    assert item == BiProduct(name="to_return and instead_of product name")
    assert_deps(deps, {"page": BiProductPage})


@attrs.define
class ProductFromInjectable:
    name: str


@handle_urls(URL, to_return=ProductFromInjectable)
class ProductFromInjectablePage(Injectable):
    @field
    def name(self) -> str:
        return "product from injectable"

    async def to_item(self) -> ProductFromInjectable:
        return await item_from_fields(self, item_cls=ProductFromInjectable)


@inlineCallbacks
def test_item_return_from_injectable() -> None:
    """The case wherein a PageObject inherits directly from ``web_poet.Injectable``
    should also work, provided that the ``to_item`` method is similar with
    ``web_poet.ItemPage``:
    """
    item, deps = yield crawl_item_and_deps(ProductFromInjectable)
    assert item == ProductFromInjectable(name="product from injectable")
    assert_deps(deps, {"item": ProductFromInjectable})

    # calling the actual Page Object should not work since it's not inheriting
    # from ``web_poet.ItemPage``.
    item, deps = yield crawl_item_and_deps(ProductFromInjectablePage)
    assert item is None

    # However, the Page Object should still be injected into the callback method.
    assert_deps(deps, {"item": ProductFromInjectablePage})


@handle_urls(URL)
class PageObjectDependencyPage(ItemPage):
    def to_item(self) -> str:
        return {"name": "item dependency"}


@attrs.define
class MainProductA:
    name: str
    item_from_po_dependency: dict


class ReplacedProductPageObjectDepPage(ItemPage):
    pass


@handle_urls(URL, instead_of=ReplacedProductPageObjectDepPage)
@attrs.define
class ProductWithPageObjectDepPage(ItemPage[MainProductA]):
    injected_page: PageObjectDependencyPage

    @field
    def name(self) -> str:
        return "(with item dependency) product name"

    @field
    def item_from_po_dependency(self) -> dict:
        return self.injected_page.to_item()


@inlineCallbacks
def test_page_object_with_page_object_dependency() -> None:
    # item from 'to_return'
    item, deps = yield crawl_item_and_deps(MainProductA)
    assert item == MainProductA(
        name="(with item dependency) product name",
        item_from_po_dependency={"name": "item dependency"},
    )
    assert_deps(deps, {"item": MainProductA})

    # item from 'instead_of'
    item, deps = yield crawl_item_and_deps(ReplacedProductPageObjectDepPage)
    assert item == MainProductA(
        name="(with item dependency) product name",
        item_from_po_dependency={"name": "item dependency"},
    )
    assert_deps(deps, {"page": ProductWithPageObjectDepPage})

    # calling the actual Page Objects should still work

    item, deps = yield crawl_item_and_deps(PageObjectDependencyPage)
    assert item == {"name": "item dependency"}
    assert_deps(deps, {"page": PageObjectDependencyPage})

    item, deps = yield crawl_item_and_deps(ProductWithPageObjectDepPage)
    assert item == MainProductA(
        name="(with item dependency) product name",
        item_from_po_dependency={"name": "item dependency"},
    )
    assert_deps(deps, {"page": ProductWithPageObjectDepPage})


@attrs.define
class ItemDependency:
    name: str


@handle_urls(URL)
class ItemDependencyPage(ItemPage[ItemDependency]):
    @field
    def name(self) -> str:
        return "item dependency"


@attrs.define
class MainProductB:
    name: str
    item_dependency: ItemDependency


class ReplacedProductItemDepPage(ItemPage):
    pass


@handle_urls(URL, instead_of=ReplacedProductItemDepPage)
@attrs.define
class ProductWithItemDepPage(ItemPage[MainProductB]):
    injected_item: ItemDependency

    @field
    def name(self) -> str:
        return "(with item dependency) product name"

    @field
    def item_dependency(self) -> ItemDependency:
        return self.injected_item


@inlineCallbacks
def test_page_object_with_item_dependency() -> None:
    """Page Objects with dependencies like item classes should have them resolved
    by the Page Object assigned in one of the rules' ``use`` parameter.
    """

    # item from 'to_return'
    item, deps = yield crawl_item_and_deps(MainProductB)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"item": MainProductB})

    # item from 'instead_of'
    item, deps = yield crawl_item_and_deps(ReplacedProductItemDepPage)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"page": ProductWithItemDepPage})

    # calling the actual Page Objects should still work

    item, deps = yield crawl_item_and_deps(ItemDependencyPage)
    assert item == ItemDependency(name="item dependency")
    assert_deps(deps, {"page": ItemDependencyPage})

    item, deps = yield crawl_item_and_deps(ProductWithItemDepPage)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"page": ProductWithItemDepPage})


def test_created_apply_rules() -> None:
    """Checks if the ``ApplyRules`` were created properly by ``@handle_urls`` in
    ``tests/po_lib/__init__.py``.
    """

    RULES = default_registry.get_rules()

    assert RULES == [
        # PageObject-based rules
        ApplyRule(URL, use=ReplacementPage, instead_of=OverriddenPage),
        # Item-based rules
        ApplyRule(URL, use=ProductPage, to_return=Product),
        ApplyRule(URL, use=ParentProductPage, to_return=ProductFromParent),
        ApplyRule(URL, use=SubclassProductPage, to_return=ProductFromParent),
        ApplyRule(
            Patterns([URL], priority=600),
            use=PriorityParentProductPage,
            to_return=PriorityProductFromParent,
        ),
        ApplyRule(
            Patterns([URL]),
            use=PrioritySubclassProductPage,
            to_return=PriorityProductFromParent,
        ),
        ApplyRule(URL, use=ReplacedProductPage, to_return=ReplacedProduct),
        ApplyRule(URL, use=ParentReplacedProductPage, to_return=ParentReplacedProduct),
        ApplyRule(
            URL, use=SubclassReplacedProductPage, to_return=SubclassReplacedProduct
        ),
        ApplyRule(URL, use=StandaloneProductPage, to_return=StandaloneProduct),
        ApplyRule(
            URL,
            use=BiProductPage,
            to_return=BiProduct,
            instead_of=ReplacedBiProductPage,
        ),
        ApplyRule(URL, use=ProductFromInjectablePage, to_return=ProductFromInjectable),
        ApplyRule(URL, use=PageObjectDependencyPage),
        ApplyRule(
            URL,
            use=ProductWithPageObjectDepPage,
            to_return=MainProductA,
            instead_of=ReplacedProductPageObjectDepPage,
        ),
        ApplyRule(URL, use=ItemDependencyPage, to_return=ItemDependency),
        ApplyRule(
            URL,
            use=ProductWithItemDepPage,
            to_return=MainProductB,
            instead_of=ReplacedProductItemDepPage,
        ),
    ]
