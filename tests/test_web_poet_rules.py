"""This tests scrapy-poet's integration with web-poet most especially when
populating override settings via:

..code-block::
    from web_poet import default_registry

    SCRAPY_POET_OVERRIDES = default_registry.get_rules()
"""

from typing import Any

from pytest_twisted import inlineCallbacks
from url_matcher import Patterns
from web_poet import ApplyRule, default_registry

from tests.po_lib import (
    PORT,
    URL,
    ParentProduct,
    ParentProductPage,
    ParentReplacedProduct,
    ParentReplacedProductPage,
    POIntegrationPage,
    POOverridenPage,
    Product,
    ProductFromInjectable,
    ProductFromInjectablePage,
    ProductPage,
    ReplacedProduct,
    ReplacedProductPage,
    StandaloneProduct,
    StandaloneProductPage,
    SubclassProductPage,
    SubclassReplacedProduct,
    SubclassReplacedProductPage,
)
from tests.test_middleware import ProductHtml, spider_for
from tests.utils import crawl_single_item, create_scrapy_settings

# The rules are defined in `tests/po_lib/__init__.py`.
RULES = default_registry.get_rules()


def rules_settings() -> dict:
    settings = create_scrapy_settings(None)
    # Converting it to a set removes potential duplicate ApplyRules
    settings["SCRAPY_POET_OVERRIDES"] = set(RULES)
    return settings


@inlineCallbacks
def crawl_item(PageObject) -> Any:
    """Helper function to easily return the item from a simulated Scrapy callback
    which asks for either of these dependencies:
        - Page Object
        - Item Type
    """
    item, _, _ = yield crawl_single_item(
        spider_for(PageObject), ProductHtml, rules_settings(), port=PORT
    )
    return item


@inlineCallbacks
def test_overrides() -> None:
    """This tests the rules where a PageObject is used in lieu of another."""
    item = yield crawl_item(POOverridenPage)
    assert item == {"msg": "PO replacement"}


@inlineCallbacks
def test_item_return() -> None:
    """This tests the rules where an Item Type is requested.

    A corresponding ``ApplyRule`` should be available to denote that a Page
    Object is equipped to produce it for the given URL pattern and Item Type.

    For example, the code below should return a ``Product`` item which was taken
    using the route ``Returns[ItemType]``.

    ..code-block::

        @handle_urls(URL)
        class ProductPage(ItemPage[Product]):
            ...
    """
    item = yield crawl_item(Product)
    assert item == Product(name="product's name")


@inlineCallbacks
def test_item_return_subclass() -> None:
    """A Page Object should properly inherit the ``Return[ItemType]`` from its
    parent.

    For the example below, asking for ParentProduct would return ``ParentProduct``
    from the ``ParentProductPage`` since the rules have equal priority but the
    ``ParentProductPage`` has been decleared first.

    ..code-block::

        @handle_urls(URL)
        class ParentProductPage(ItemPage[ParentProduct]):
            ...

        @handle_urls(URL)
        class SubclassProductPage(ParentProductPage):
            ...

    If users want to use the ``ParentProduct`` coming from ``SubclassProductPage``,
    then they'd need to increase the priority:

    ..code-block::

        @handle_urls(URL, priority=600)
        class SubclassProductPage(ParentProductPage):
            ...

    """
    item = yield crawl_item(ParentProduct)
    assert item == ParentProduct(name="subclass product's name")


# FIXME: tests failing since the PO's to_item() method hasn't been affected by
#        the 'to_return' parameter change.
# TODO: Consider "skip_nonitem_fields" for the cases below
@inlineCallbacks
def test_item_return_replaced_by_to_return() -> None:
    """The ``to_return`` parameter passed in ``@handle_urls()`` should be used
    instead of the underlying ``Returns[ItemType]`` inside the Page Object.

    For example, in the code below, the returned item should be ``ReplacedProduct(...)``.

    ..code-block::

        @handle_urls(URL, to_return=ReplacedProduct)
        class ReplacedProductPage(ItemPage[Product]):
            ...
    """
    item = yield crawl_item(ReplacedProduct)
    assert item == ReplacedProduct(name="replaced product's name")


# FIXME: same case as above
@inlineCallbacks
def test_item_return_replaced_by_to_return_in_subclass() -> None:
    """Same case as with the ``test_item_return_replaced_by_to_return()`` case
    above but the ``to_return`` replacement is done in the subclass.

    In the example below, requesting a ``SubclassReplacedProduct`` item should
    come from the ``SubclassReplacedProductPage`` page object.

    ..code-block::

        @handle_urls(URL)
        class ParentReplacedProductPage(ItemPage[ParentReplacedProduct]):
            ...

        @handle_urls(URL, to_return=SubclassReplacedProduct)
        class SubclassReplacedProductPage(ParentReplacedProductPage):
            ...
    """
    item = yield crawl_item(SubclassReplacedProduct)
    assert item == SubclassReplacedProduct(name="subclass replaced product's name")


# FIXME: tests failing since it returns a ``dict``; same case as above
@inlineCallbacks
def test_item_return_standalone() -> None:
    """Despite the PageObject not having ``Returns[ItemType]``, a return type
    should still be able to work using the ``to_return`` parameter passed in the
    ``@handle_urls()`` decorator.

    For example, the following code below should return a ``StandaloneProduct``
    item.

    ..code-block::

        @handle_urls(URL, to_return=StandaloneProduct)
        class StandaloneProductPage(ItemPage):
            ...
    """
    item = yield crawl_item(StandaloneProduct)
    assert item == StandaloneProduct(name="standalone product's name")


@inlineCallbacks
def test_item_return_from_injectable() -> None:
    """The case wherein a PageObject inherits directly from ``web_poet.Injectable``
    should also work, provided that the ``to_item`` method is similar with
    ``web_poet.ItemPage``:

    ..code-block::
        @handle_urls(URL, to_return=ProductFromInjectable)
        class ProductFromInjectablePage(Injectable):
            @field
            def name(self) -> str:
                return "product from injectable"

            async def to_item(self) -> ProductFromInjectable:
                return await item_from_fields(self, item_cls=ProductFromInjectable)

    """
    item = yield crawl_item(ProductFromInjectable)
    assert item == ProductFromInjectable(name="product from injectable")


def test_created_apply_rules() -> None:
    """Checks if the ``ApplyRules`` were created properly by ``@handle_urls`` in
    ``tests/po_lib/__init__.py``.
    """

    assert RULES == [
        # PageObject-based rules
        ApplyRule(URL, use=POIntegrationPage, instead_of=POOverridenPage),
        # Item-based rules
        ApplyRule(URL, use=ProductPage, to_return=Product),
        ApplyRule(URL, use=ParentProductPage, to_return=ParentProduct),
        ApplyRule(
            Patterns([URL], priority=600),
            use=SubclassProductPage,
            to_return=ParentProduct,
        ),
        ApplyRule(URL, use=ReplacedProductPage, to_return=ReplacedProduct),
        ApplyRule(URL, use=ParentReplacedProductPage, to_return=ParentReplacedProduct),
        ApplyRule(
            URL, use=SubclassReplacedProductPage, to_return=SubclassReplacedProduct
        ),
        ApplyRule(URL, use=StandaloneProductPage, to_return=StandaloneProduct),
        ApplyRule(URL, use=ProductFromInjectablePage, to_return=ProductFromInjectable),
    ]
