"""This tests scrapy-poet's integration with web-poet's ``ApplyRule`` specifically
when used for callback dependencies.

Most of the logic here tests the behavior of the ``scrapy_poet/injection.py``
and ``scrapy_poet/registry.py`` modules.
"""

import socket
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Type

import attrs
import scrapy
from pytest_twisted import inlineCallbacks
from typing_extensions import Annotated
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
from web_poet.pages import ItemT

from scrapy_poet import PickFields, callback_for
from scrapy_poet.downloadermiddlewares import DEFAULT_PROVIDERS
from scrapy_poet.utils.mockserver import get_ephemeral_port
from scrapy_poet.utils.testing import (
    capture_exceptions,
    crawl_single_item,
    create_scrapy_settings,
)
from tests.test_middleware import ProductHtml

DOMAIN = get_domain(socket.gethostbyname(socket.gethostname()))
PORT = get_ephemeral_port()
URL = f"{DOMAIN}:{PORT}"


def rules_settings() -> dict:
    settings = create_scrapy_settings(None)
    settings["SCRAPY_POET_RULES"] = default_registry.get_rules()
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


class PageObjectCounterMixin:
    """Inherited by some POs in a few of the tests which has a deep dependency
    tree.

    This is mostly used to ensure that class instances are not duplicated when
    building out the dependency tree as they could get expensive.

    For example, a PO could have its ``.to_item()`` method called multiple times
    to produce the same item. This is extremely wasteful should there be any
    additional requests used to produce the item.

    ``ItemProvider`` should cache up such instances and prevent them from being
    built again.
    """

    instances: Dict[Type, Any] = defaultdict(list)
    to_item_call_count = 0

    def __attrs_pre_init__(self):
        self.instances[type(self)].append(self)

    @classmethod
    def assert_instance_count(cls, count, type_):
        assert len(cls.instances[type_]) == count, type_

    @classmethod
    def clear(cls):
        for po_cls in cls.instances.keys():
            po_cls.to_item_call_count = 0
        cls.instances = defaultdict(list)

    async def to_item(self) -> ItemT:
        type(self).to_item_call_count += 1
        return await super().to_item()


@inlineCallbacks
def crawl_item_and_deps(
    page_object: Optional[ItemPage], spider: Optional[scrapy.Spider] = None
) -> Tuple[Any, Any]:
    """Helper function to easily return the item and injected dependencies from
    a simulated Scrapy callback which asks for either of these dependencies:
        - page object
        - item class
    """
    spider = spider or spider_for(page_object)
    item, _, crawler = yield crawl_single_item(
        spider, ProductHtml, rules_settings(), port=PORT
    )
    return item, crawler.spider.collected_response_deps


def assert_deps(deps: List[Dict[str, Any]], expected: Dict[str, Any], size: int = 1):
    """Helper for easily checking the instances of the ``deps`` returned by
    ``crawl_item_and_deps()``.

    The ``deps`` and ``expected`` follow a dict-formatted **kwargs parameters
    that is passed to the spider callback. Currently, either "page" or "item"
    are supported as keys since ``scrapy_poet.callback`` is used.
    """
    assert len(deps) == size
    if size == 0:
        return

    # Only checks the first element for now since it's used alongside crawling
    # a single item.
    assert not deps[0].keys() - expected.keys()
    assert all([True for k, v in expected.items() if isinstance(deps[0][k], v)])


@handle_urls(URL)
class UrlMatchPage(ItemPage):
    async def to_item(self) -> dict:
        return {"msg": "PO URL Match"}


@inlineCallbacks
def test_url_only_match() -> None:
    """Page Objects which only have URL in its ``@handle_urls`` annotation should
    work.
    """
    item, deps = yield crawl_item_and_deps(UrlMatchPage)
    assert item == {"msg": "PO URL Match"}
    assert_deps(deps, {"page": UrlMatchPage})


@handle_urls("example.com")
class UrlNoMatchPage(ItemPage):
    async def to_item(self) -> dict:
        return {"msg": "PO No URL Match"}


@inlineCallbacks
def test_url_only_no_match() -> None:
    """Same case as with ``test_url_only_match()`` but the URL specified in the
    ``@handle_urls`` annotation doesn't match the request/response URL that the
    spider is crawling.

    However, it should still work since we're forcing to use ``UrlNoMatchPage``
    specifically as the page object input.
    """
    item, deps = yield crawl_item_and_deps(UrlNoMatchPage)
    assert item == {"msg": "PO No URL Match"}
    assert_deps(deps, {"page": UrlNoMatchPage})


class NoRulePage(ItemPage):
    async def to_item(self) -> dict:
        return {"msg": "NO Rule"}


class NoRuleWebPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "NO Rule Web"}


@inlineCallbacks
def test_no_rule_declaration() -> None:
    """A more extreme case of ``test_url_only_no_match()`` where the page object
    doesn't have any rule declaration at all.

    But it should still work since we're enforcing the dependency.
    """
    item, deps = yield crawl_item_and_deps(NoRulePage)
    assert item == {"msg": "NO Rule"}
    assert_deps(deps, {"page": NoRulePage})

    item, deps = yield crawl_item_and_deps(NoRuleWebPage)
    assert item == {"msg": "NO Rule Web"}
    assert_deps(deps, {"page": NoRuleWebPage})


class OverriddenPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "PO that will be replaced"}


@handle_urls(URL, instead_of=OverriddenPage)
class ReplacementPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "PO replacement"}


@inlineCallbacks
def test_basic_overrides() -> None:
    """Basic overrides use case.

    If a page object is asked for and it's available in a rule's ``instead_of``
    parameter, it would be replaced by the page object inside the rule's ``use``
    parameter.
    """
    item, deps = yield crawl_item_and_deps(OverriddenPage)
    assert item == {"msg": "PO replacement"}
    assert_deps(deps, {"page": ReplacementPage})

    # Calling the replacement should also still work
    item, deps = yield crawl_item_and_deps(ReplacementPage)
    assert item == {"msg": "PO replacement"}
    assert_deps(deps, {"page": ReplacementPage})


class LeftPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "left page"}


@handle_urls(URL, instead_of=LeftPage)
class RightPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "right page"}


# We define it here since it errors out if made as a decorator
# since RightPage doesn't exist yet.
handle_urls(URL, instead_of=RightPage)(LeftPage)


@inlineCallbacks
def test_mutual_overrides() -> None:
    """Two page objects that override each other should not present any problems.

    In practice, this isn't useful at all.

    TODO: We could present a warning to the user if this is detected.
    THOUGHTS:
        Although I doubt this would be common in most code bases since this would
        only be possible if we do `handle_urls(URL, instead_of=RightPage)(LeftPage)`
        which is highly unnatural.

        Another instance that it might occur is when users don't use `handle_urls()`
        to write the rules but create a list of `ApplyRules` manually and passing
        them to the `SCRAPY_POET_RULES` setting. I'm also not sure how common
        this would be against simply using `@handle_urls()`.

        Let's hold off this potential warning mechanism until we observe that it
        actually affects users.
    """
    item, deps = yield crawl_item_and_deps(LeftPage)
    assert item == {"msg": "right page"}
    assert_deps(deps, {"page": RightPage})

    item, deps = yield crawl_item_and_deps(RightPage)
    assert item == {"msg": "left page"}
    assert_deps(deps, {"page": LeftPage})


@handle_urls(URL)
class NewHopePage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "new hope"}


@handle_urls(URL, instead_of=NewHopePage)
class EmpireStrikesBackPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "empire strikes back"}


@handle_urls(URL, instead_of=EmpireStrikesBackPage)
class ReturnOfTheJediPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "return of the jedi"}


@inlineCallbacks
def test_chained_overrides() -> None:
    """If 3 overrides are connected to each other, there wouldn't be any
    transitivity than spans the 3 POs.
    """
    item, deps = yield crawl_item_and_deps(NewHopePage)
    assert item == {"msg": "empire strikes back"}
    assert_deps(deps, {"page": EmpireStrikesBackPage})

    # Calling the other PO should still work

    item, deps = yield crawl_item_and_deps(EmpireStrikesBackPage)
    assert item == {"msg": "return of the jedi"}
    assert_deps(deps, {"page": ReturnOfTheJediPage})

    item, deps = yield crawl_item_and_deps(ReturnOfTheJediPage)
    assert item == {"msg": "return of the jedi"}
    assert_deps(deps, {"page": ReturnOfTheJediPage})


@handle_urls(URL)
class FirstPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "First page"}


@handle_urls(URL)
class SecondPage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "Second page"}


@handle_urls(URL, instead_of=FirstPage)
@handle_urls(URL, instead_of=SecondPage)
class MultipleRulePage(WebPage):
    async def to_item(self) -> dict:
        return {"msg": "multiple rule page"}


@inlineCallbacks
def test_multiple_rules_single_page_object() -> None:
    """A single PO could be used by multiple other rules."""
    item, deps = yield crawl_item_and_deps(FirstPage)
    assert item == {"msg": "multiple rule page"}
    assert_deps(deps, {"page": MultipleRulePage})

    item, deps = yield crawl_item_and_deps(SecondPage)
    assert item == {"msg": "multiple rule page"}
    assert_deps(deps, {"page": MultipleRulePage})

    # Calling the replacement should also still work
    item, deps = yield crawl_item_and_deps(MultipleRulePage)
    assert item == {"msg": "multiple rule page"}
    assert_deps(deps, {"page": MultipleRulePage})


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

    If an item class is asked for and it's available in some rule's ``to_return``
    parameter, an item class's instance shall be produced by the page object
    declared inside the rule's ``use`` parameter.
    """
    item, deps = yield crawl_item_and_deps(Product)
    assert item == Product(name="product name")
    assert_deps(deps, {"item": Product})

    # calling the actual page object should also work
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
    """A page object should properly derive the ``Return[ItemType]`` that it
    inherited from its parent.

    In this test case, there's a clash for the ``url_matcher.Patterns`` since
    they're exactly the same. This produces a warning message. For conflicts
    like this, scrapy-poet follows the first ``ApplyRule`` it finds inside the
    ``SCRAPY_POET_RULES`` setting.

    To remove this warning, the user should update the priority in
    ``url_matcher.Patterns`` which is set in ``ApplyRule.for_patterns``.
    """

    # There should be a warning to the user about clashing rules.
    rules = [
        ApplyRule(URL, use=ParentProductPage, to_return=ProductFromParent),
        ApplyRule(URL, use=SubclassProductPage, to_return=ProductFromParent),
    ]
    msg = f"Consider updating the priority of these rules: {rules}"

    with warnings.catch_warnings(record=True) as caught_warnings:
        item, deps = yield crawl_item_and_deps(ProductFromParent)
        assert any([True for w in caught_warnings if msg in str(w.message)])

    assert item == ProductFromParent(name="subclass product name")
    assert_deps(deps, {"item": ProductFromParent})

    # calling the actual page objects should still work

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

    # calling the actual page objects should still work

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
def test_item_to_return_in_handle_urls(caplog) -> None:
    """Even if ``@handle_urls`` could derive the value for the ``to_return``
    parameter when the class inherits from something like ``ItemPage[ItemType]``,
    any value passed through its ``to_return`` parameter should take precedence.

    Note that that this produces some inconsistencies between the rule's item
    class vs the class that is actually returned. Using the ``to_return``
    parameter in ``@handle_urls`` isn't recommended because of this.

    This also causes an ``UndeclaredProvidedTypeError`` since the item provider
    has received a different type of item class from the page object.
    """
    item, deps = yield crawl_item_and_deps(ReplacedProduct)
    assert "UndeclaredProvidedTypeError:" in caplog.text
    assert item is None
    assert_deps(deps, {}, size=0)

    # Requesting the underlying item class from the PO should still work.
    item, deps = yield crawl_item_and_deps(Product)
    assert item == Product(name="product name")
    assert_deps(deps, {"item": Product})

    # calling the actual page objects should still work
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
def test_item_to_return_in_handle_urls_subclass(caplog) -> None:
    """Same case as with the ``test_item_to_return_in_handle_urls()`` case above
    but the ``to_return`` is declared in the subclass.
    """
    item, deps = yield crawl_item_and_deps(SubclassReplacedProduct)
    assert "UndeclaredProvidedTypeError:" in caplog.text
    assert item is None
    assert_deps(deps, {}, size=0)

    # Requesting the underlying item class from the parent PO should still work.
    item, deps = yield crawl_item_and_deps(ParentReplacedProduct)
    assert item == ParentReplacedProduct(name="parent replaced product name")
    assert_deps(deps, {"item": ParentReplacedProduct})

    # calling the actual page objects should still work

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
def test_item_to_return_standalone(caplog) -> None:
    """Same case as with ``test_item_to_return_in_handle_urls()`` above but the
    page object doesn't inherit from something like ``ItemPage[ItemClass]``
    """
    item, deps = yield crawl_item_and_deps(StandaloneProduct)
    assert "UndeclaredProvidedTypeError:" in caplog.text
    assert item is None
    assert_deps(deps, {}, size=0)

    # calling the actual page object should still work
    item, deps = yield crawl_item_and_deps(StandaloneProductPage)
    assert item == {"name": "standalone product name"}
    assert_deps(deps, {"page": StandaloneProductPage})


@attrs.define
class Morty:
    name: str


@handle_urls(URL)
class RickSanchezPage(ItemPage[Morty]):
    @field
    def name(self) -> str:
        return "from basic rick"


@handle_urls(URL, instead_of=RickSanchezPage)
class RickSanchezC137Page(ItemPage[Morty]):
    @field
    def name(self) -> str:
        return "wubba lubba dub dub"


@inlineCallbacks
def test_item_return_with_overrides() -> None:
    item, deps = yield crawl_item_and_deps(Morty)
    assert item == Morty(name="wubba lubba dub dub")
    assert_deps(deps, {"item": RickSanchezC137Page})

    # page from 'instead_of'
    item, deps = yield crawl_item_and_deps(RickSanchezPage)
    assert item == Morty(name="wubba lubba dub dub")
    assert_deps(deps, {"page": RickSanchezC137Page})

    # calling the actual page object should still work
    item, deps = yield crawl_item_and_deps(RickSanchezC137Page)
    assert item == Morty(name="wubba lubba dub dub")
    assert_deps(deps, {"page": RickSanchezC137Page})


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

    # calling the actual page object should not work since it's not inheriting
    # from ``web_poet.ItemPage``.
    item, deps = yield crawl_item_and_deps(ProductFromInjectablePage)
    assert item is None

    # However, the page object should still be injected into the callback method.
    assert_deps(deps, {"item": ProductFromInjectablePage})


@handle_urls(URL)
class PageObjectDependencyPage(ItemPage):
    async def to_item(self) -> dict:
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
    async def item_from_po_dependency(self) -> dict:
        return await self.injected_page.to_item()


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

    # calling the actual page objects should still work

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
@attrs.define
class ItemDependencyPage(PageObjectCounterMixin, ItemPage[ItemDependency]):
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
class ProductWithItemDepPage(PageObjectCounterMixin, ItemPage[MainProductB]):
    injected_item: ItemDependency

    @field
    def name(self) -> str:
        return "(with item dependency) product name"

    @field
    def item_dependency(self) -> ItemDependency:
        return self.injected_item


@inlineCallbacks
def test_page_object_with_item_dependency() -> None:
    """Page objects with dependencies like item classes should have them resolved
    by the page object assigned in one of the rules' ``use`` parameter.
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

    # calling the actual page objects should still work

    item, deps = yield crawl_item_and_deps(ItemDependencyPage)
    assert item == ItemDependency(name="item dependency")
    assert_deps(deps, {"page": ItemDependencyPage})

    item, deps = yield crawl_item_and_deps(ProductWithItemDepPage)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"page": ProductWithItemDepPage})

    # Calling the original dependency should still work
    item, deps = yield crawl_item_and_deps(ItemDependency)
    assert item == ItemDependency(name="item dependency")
    assert_deps(deps, {"item": ItemDependency})


@attrs.define
class MainProductC:
    name: str
    item_dependency: ItemDependency
    main_product_b_dependency: MainProductB


@handle_urls(URL)
@attrs.define
class ProductDeepDependencyPage(PageObjectCounterMixin, ItemPage[MainProductC]):
    injected_item: ItemDependency
    main_product_b_dependency_item: MainProductB

    @field
    def name(self) -> str:
        return "(with deep item dependency) product name"

    @field
    def item_dependency(self) -> ItemDependency:
        return self.injected_item

    @field
    def main_product_b_dependency(self) -> MainProductB:
        return self.main_product_b_dependency_item


@inlineCallbacks
def test_page_object_with_deep_item_dependency() -> None:
    """This builds upon the earlier ``test_page_object_with_item_dependency()``
    but with another layer of item dependencies.
    """

    # item from 'to_return'
    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(MainProductC)
    assert item == MainProductC(
        name="(with deep item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
        main_product_b_dependency=MainProductB(
            name="(with item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
        ),
    )
    assert_deps(deps, {"item": MainProductC})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 1

    # calling the actual page objects should still work

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(ProductDeepDependencyPage)
    assert item == MainProductC(
        name="(with deep item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
        main_product_b_dependency=MainProductB(
            name="(with item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
        ),
    )
    assert_deps(deps, {"page": ProductDeepDependencyPage})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 1

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(ItemDependencyPage)
    assert item == ItemDependency(name="item dependency")
    assert_deps(deps, {"page": ItemDependencyPage})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 0
    assert ProductDeepDependencyPage.to_item_call_count == 0

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(ProductWithItemDepPage)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"page": ProductWithItemDepPage})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 0

    # Calling the other item dependencies should still work

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(MainProductB)
    assert item == MainProductB(
        name="(with item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
    )
    assert_deps(deps, {"item": MainProductB})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 0

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(ItemDependency)
    assert item == ItemDependency(name="item dependency")
    assert_deps(deps, {"item": ItemDependency})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(0, ProductDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 0
    assert ProductDeepDependencyPage.to_item_call_count == 0


@attrs.define
class MainProductD:
    name: str
    item_dependency: ItemDependency
    main_product_b_dependency: MainProductB
    first_main_product_c_dependency: MainProductC
    second_main_product_c_dependency: MainProductC


@handle_urls(URL)
@attrs.define
class ProductDuplicateDeepDependencyPage(
    PageObjectCounterMixin, ItemPage[MainProductD]
):
    injected_item: ItemDependency
    main_product_b_dependency_item: MainProductB
    first_main_product_c_dependency_item: MainProductC
    second_main_product_c_dependency_item: MainProductC

    @field
    def name(self) -> str:
        return "(with duplicate deep item dependency) product name"

    @field
    def item_dependency(self) -> ItemDependency:
        return self.injected_item

    @field
    def main_product_b_dependency(self) -> MainProductB:
        return self.main_product_b_dependency_item

    @field
    def first_main_product_c_dependency(self) -> MainProductC:
        return self.first_main_product_c_dependency_item

    @field
    def second_main_product_c_dependency(self) -> MainProductC:
        return self.second_main_product_c_dependency_item


@inlineCallbacks
def test_page_object_with_duplicate_deep_item_dependency() -> None:
    """This yet builds upon the earlier ``test_page_object_with_deep_item_dependency()``
    making it deeper.

    However, this one has some duplicated dependencies
    """

    # item from 'to_return'
    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(MainProductD)
    assert item == MainProductD(
        name="(with duplicate deep item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
        main_product_b_dependency=MainProductB(
            name="(with item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
        ),
        first_main_product_c_dependency=MainProductC(
            name="(with deep item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
            main_product_b_dependency=MainProductB(
                name="(with item dependency) product name",
                item_dependency=ItemDependency(name="item dependency"),
            ),
        ),
        second_main_product_c_dependency=MainProductC(
            name="(with deep item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
            main_product_b_dependency=MainProductB(
                name="(with item dependency) product name",
                item_dependency=ItemDependency(name="item dependency"),
            ),
        ),
    )
    assert_deps(deps, {"item": MainProductD})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDeepDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDuplicateDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 1
    assert ProductDuplicateDeepDependencyPage.to_item_call_count == 1

    # calling the actual page objects should still work

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(ProductDuplicateDeepDependencyPage)
    assert item == MainProductD(
        name="(with duplicate deep item dependency) product name",
        item_dependency=ItemDependency(name="item dependency"),
        main_product_b_dependency=MainProductB(
            name="(with item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
        ),
        first_main_product_c_dependency=MainProductC(
            name="(with deep item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
            main_product_b_dependency=MainProductB(
                name="(with item dependency) product name",
                item_dependency=ItemDependency(name="item dependency"),
            ),
        ),
        second_main_product_c_dependency=MainProductC(
            name="(with deep item dependency) product name",
            item_dependency=ItemDependency(name="item dependency"),
            main_product_b_dependency=MainProductB(
                name="(with item dependency) product name",
                item_dependency=ItemDependency(name="item dependency"),
            ),
        ),
    )
    assert_deps(deps, {"page": ProductDuplicateDeepDependencyPage})
    PageObjectCounterMixin.assert_instance_count(1, ItemDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductWithItemDepPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDeepDependencyPage)
    PageObjectCounterMixin.assert_instance_count(1, ProductDuplicateDeepDependencyPage)
    assert ItemDependencyPage.to_item_call_count == 1
    assert ProductWithItemDepPage.to_item_call_count == 1
    assert ProductDeepDependencyPage.to_item_call_count == 1
    assert ProductDuplicateDeepDependencyPage.to_item_call_count == 1


@attrs.define
class ChickenPage:
    name: str
    other: str


@attrs.define
class EggPage:
    name: str
    other: str


@handle_urls(URL)
@attrs.define
class ChickenDeadlockPage(ItemPage[ChickenPage]):
    other_injected: EggPage

    @field
    def name(self) -> str:
        return "chicken"

    @field
    def other(self) -> str:
        return self.other_injected.name


@handle_urls(URL)
@attrs.define
class EggDeadlockPage(ItemPage[EggPage]):
    other_injected: ChickenPage

    @field
    def name(self) -> str:
        return "egg"

    @field
    def other(self) -> str:
        return self.other_injected.name


@inlineCallbacks
def test_page_object_with_item_dependency_deadlock(caplog) -> None:
    """Items with page objects which depend on each other resulting in a deadlock
    should have a corresponding error raised.
    """

    item, deps = yield crawl_item_and_deps(ChickenPage)
    assert "ProviderDependencyDeadlockError" in caplog.text

    item, deps = yield crawl_item_and_deps(EggPage)
    assert "ProviderDependencyDeadlockError" in caplog.text


@attrs.define
class BigItem:
    x: str
    y: Optional[str] = None


@handle_urls(URL)
@attrs.define
class BigPage(PageObjectCounterMixin, ItemPage[BigItem]):
    @field
    def x(self) -> str:
        return "x"

    @field
    def y(self) -> str:
        return "y"


class BigSpider(scrapy.Spider):
    name = "bigspider"
    url = None
    custom_settings = {
        "SCRAPY_POET_PROVIDERS": DEFAULT_PROVIDERS,
    }

    def start_requests(self):
        yield scrapy.Request(self.url, capture_exceptions(self.parse))

    def parse(self, response, item: Annotated[BigItem, PickFields("x")]):
        yield item


@inlineCallbacks
def test_page_object_pick_fields() -> None:
    """Spider callbacks annotated with ``PickFields`` should only return the
    requested field and completely avoid calling ``.to_item()``.
    """

    PageObjectCounterMixin.clear()
    item, deps = yield crawl_item_and_deps(None, BigSpider)
    assert item == BigItem(x="x")
    assert_deps(deps, {"item": BigItem})
    PageObjectCounterMixin.assert_instance_count(1, BigPage)
    assert BigPage.to_item_call_count == 0


def test_created_apply_rules() -> None:
    """Checks if the ``ApplyRules`` were created properly by ``@handle_urls`` in
    ``tests/po_lib/__init__.py``.
    """

    RULES = default_registry.get_rules()

    assert RULES == [
        # URL declaration only
        ApplyRule(URL, use=UrlMatchPage),
        ApplyRule("example.com", use=UrlNoMatchPage),
        # PageObject-based rules
        ApplyRule(URL, use=ReplacementPage, instead_of=OverriddenPage),
        ApplyRule(URL, use=RightPage, instead_of=LeftPage),
        ApplyRule(URL, use=LeftPage, instead_of=RightPage),
        ApplyRule(URL, use=NewHopePage),
        ApplyRule(URL, use=EmpireStrikesBackPage, instead_of=NewHopePage),
        ApplyRule(URL, use=ReturnOfTheJediPage, instead_of=EmpireStrikesBackPage),
        ApplyRule(URL, use=FirstPage),
        ApplyRule(URL, use=SecondPage),
        ApplyRule(URL, use=MultipleRulePage, instead_of=SecondPage),
        ApplyRule(URL, use=MultipleRulePage, instead_of=FirstPage),
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
        ApplyRule(URL, use=RickSanchezPage, to_return=Morty),
        ApplyRule(
            URL,
            use=RickSanchezC137Page,
            to_return=Morty,
            instead_of=RickSanchezPage,
        ),
        ApplyRule(
            URL,
            # We're ignoring the typing here since it expects the argument for
            # use to be a subclass of ItemPage.
            use=ProductFromInjectablePage,  # type: ignore[arg-type]
            to_return=ProductFromInjectable,
        ),
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
        ApplyRule(URL, use=ProductDeepDependencyPage, to_return=MainProductC),
        ApplyRule(URL, use=ProductDuplicateDeepDependencyPage, to_return=MainProductD),
        ApplyRule(URL, use=ChickenDeadlockPage, to_return=ChickenPage),
        ApplyRule(URL, use=EggDeadlockPage, to_return=EggPage),
        ApplyRule(URL, use=BigPage, to_return=BigItem),
    ]
