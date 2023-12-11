import shutil

import attr
import parsel
import pytest
from pytest_twisted import inlineCallbacks
from scrapy import Request
from scrapy.http import Response
from url_matcher import Patterns
from url_matcher.util import get_domain
from web_poet import Injectable, ItemPage, RulesRegistry
from web_poet.mixins import ResponseShortcutsMixin
from web_poet.rules import ApplyRule

from scrapy_poet import DummyResponse, HttpResponseProvider, PageObjectInputProvider
from scrapy_poet.injection import (
    check_all_providers_are_callable,
    get_injector_for_testing,
    get_response_for_testing,
    is_class_provided_by_any_provider_fn,
)
from scrapy_poet.injection_errors import (
    InjectionError,
    NonCallableProviderError,
    UndeclaredProvidedTypeError,
)

from .test_providers import Name, Price


def get_provider(classes, content=None):
    class Provider(PageObjectInputProvider):
        provided_classes = classes
        require_response = False

        def __init__(self, crawler):
            self.crawler = crawler

        def __call__(self, to_provide):
            return [cls(content) if content else cls() for cls in classes]

    return Provider


def get_provider_requiring_response(classes):
    class Provider(PageObjectInputProvider):
        provided_classes = classes
        require_response = True

        def __init__(self, crawler):
            self.crawler = crawler

        def __call__(self, to_provide, response: Response):
            return [cls() for cls in classes]

    return Provider


class ClsReqResponse(str):
    pass


class Cls1(str):
    pass


class Cls2(str):
    pass


class ClsNoProvided(str):
    pass


class ClsNoProviderRequired(Injectable, str):
    pass


def get_providers_for_testing():
    prov1 = get_provider_requiring_response({ClsReqResponse})
    prov2 = get_provider({Cls1, Cls2})
    # Duplicating them because they should work even in this situation
    return {prov1: 1, prov2: 2, prov1: 3, prov2: 4}  # noqa: F602


@pytest.fixture
def providers():
    return get_providers_for_testing()


@pytest.fixture
def injector(providers):
    return get_injector_for_testing(providers)


@attr.s(auto_attribs=True, frozen=True, eq=True, order=True)
class WrapCls(Injectable):
    a: ClsReqResponse


class TestInjector:
    def test_constructor(self):
        injector = get_injector_for_testing(get_providers_for_testing())
        assert injector.is_class_provided_by_any_provider(ClsReqResponse)
        assert injector.is_class_provided_by_any_provider(Cls1)
        assert not injector.is_class_provided_by_any_provider(ClsNoProvided)

        for provider in injector.providers:
            assert (
                injector.is_provider_requiring_scrapy_response[provider]
                == provider.require_response
            )

    def test_non_callable_provider_error(self):
        """Checks that a exception is raised when a provider is not callable"""

        class NonCallableProvider(PageObjectInputProvider):
            pass

        with pytest.raises(NonCallableProviderError):
            get_injector_for_testing({NonCallableProvider: 1})

    def test_discover_callback_providers(self, injector, providers, request):
        def discover_fn(callback):
            request = Request("http://example.com", callback=callback)
            return injector.discover_callback_providers(request)

        providers_list = list(providers.keys())

        def callback_0(a: ClsNoProvided):
            pass

        assert set(map(type, discover_fn(callback_0))) == set()

        def callback_1(a: ClsReqResponse, b: Cls2):
            pass

        assert set(map(type, discover_fn(callback_1))) == set(providers_list)

        def callback_2(a: Cls1, b: Cls2):
            pass

        assert set(map(type, discover_fn(callback_2))) == {providers_list[1]}

        def callback_3(a: ClsNoProvided, b: WrapCls):
            pass

        assert set(map(type, discover_fn(callback_3))) == {providers_list[0]}

    def test_is_scrapy_response_required(self, injector):
        def callback_no_1(response: DummyResponse, a: Cls1):
            pass

        response = get_response_for_testing(callback_no_1)
        assert not injector.is_scrapy_response_required(response.request)

        def callback_yes_1(response, a: Cls1):
            pass

        response = get_response_for_testing(callback_yes_1)
        assert injector.is_scrapy_response_required(response.request)

        def callback_yes_2(response: DummyResponse, a: ClsReqResponse):
            pass

        response = get_response_for_testing(callback_yes_2)
        assert injector.is_scrapy_response_required(response.request)

    @inlineCallbacks
    def test_build_instances_methods(self, injector):
        def callback(
            response: DummyResponse,
            a: Cls1,
            b: Cls2,
            c: WrapCls,
            d: ClsNoProviderRequired,
        ):
            pass

        response = get_response_for_testing(callback)
        request = response.request
        plan = injector.build_plan(response.request)
        instances = yield from injector.build_instances(request, response, plan)
        assert instances == {
            Cls1: Cls1(),
            Cls2: Cls2(),
            WrapCls: WrapCls(ClsReqResponse()),
            ClsReqResponse: ClsReqResponse(),
            ClsNoProviderRequired: ClsNoProviderRequired(),
        }

        instances = yield from injector.build_instances_from_providers(
            request, response, plan
        )
        assert instances == {
            Cls1: Cls1(),
            Cls2: Cls2(),
            ClsReqResponse: ClsReqResponse(),
        }

    @inlineCallbacks
    def test_build_instances_from_providers_unexpected_return(self):
        class WrongProvider(get_provider({Cls1})):
            def __call__(self, to_provide):
                return super().__call__(to_provide) + [Cls2()]

        injector = get_injector_for_testing({WrongProvider: 0})

        def callback(response: DummyResponse, a: Cls1):
            pass

        response = get_response_for_testing(callback)
        plan = injector.build_plan(response.request)
        with pytest.raises(UndeclaredProvidedTypeError) as exinf:
            yield from injector.build_instances_from_providers(
                response.request, response, plan
            )

        assert "Provider" in str(exinf.value)
        assert "Cls2" in str(exinf.value)
        assert "Cls1" in str(exinf.value)

    @pytest.mark.parametrize(
        "str_list",
        [
            ["1", "2", "3"],
            ["3", "2", "1"],
            ["1", "3", "2"],
        ],
    )
    @inlineCallbacks
    def test_build_instances_from_providers_respect_priorities(self, str_list):
        providers = {get_provider({str}, text): int(text) for text in str_list}
        injector = get_injector_for_testing(providers)

        def callback(response: DummyResponse, arg: str):
            pass

        response = get_response_for_testing(callback)
        plan = injector.build_plan(response.request)
        instances = yield from injector.build_instances_from_providers(
            response.request, response, plan
        )

        assert instances[str] == min(str_list)

    @inlineCallbacks
    def test_build_callback_dependencies(self, injector):
        def callback(
            response: DummyResponse,
            a: Cls1,
            b: Cls2,
            c: WrapCls,
            d: ClsNoProviderRequired,
        ):
            pass

        response = get_response_for_testing(callback)
        kwargs = yield from injector.build_callback_dependencies(
            response.request, response
        )
        kwargs_types = {key: type(value) for key, value in kwargs.items()}
        assert kwargs_types == {
            "a": Cls1,
            "b": Cls2,
            "c": WrapCls,
            "d": ClsNoProviderRequired,
        }


class Html(Injectable):
    url = "http://example.com"
    text = """<html><body>Price: <span class="price">22</span>€</body></html>"""

    @property
    def selector(self):
        return parsel.Selector(self.text)


class EurDollarRate(Injectable):
    rate = 1.1


class OtherEurDollarRate(Injectable):
    rate = 2


@attr.s(auto_attribs=True)
class PricePO(ItemPage, ResponseShortcutsMixin):
    response: Html  # type: ignore[assignment]

    def to_item(self):
        return dict(price=float(self.css(".price::text").get()), currency="€")


@attr.s(auto_attribs=True)
class PriceInDollarsPO(ItemPage):
    original_po: PricePO
    conversion: EurDollarRate

    def to_item(self):
        item = self.original_po.to_item()
        item["price"] *= self.conversion.rate
        item["currency"] = "$"
        return item


@attr.s(auto_attribs=True)
class TestItem:
    foo: int
    bar: str


class TestItemPage(ItemPage[TestItem]):
    async def to_item(self):
        return TestItem(foo=1, bar="bar")


class TestInjectorStats:
    @pytest.mark.parametrize(
        "cb_args, expected",
        (
            (
                {"price_po": PricePO, "rate_po": EurDollarRate},
                {
                    "tests.test_injection.PricePO",
                    "tests.test_injection.EurDollarRate",
                    "tests.test_injection.Html",
                },
            ),
            (
                {"price_po": PriceInDollarsPO},
                {
                    "tests.test_injection.PricePO",
                    "tests.test_injection.PriceInDollarsPO",
                    "tests.test_injection.Html",
                    "tests.test_injection.EurDollarRate",
                },
            ),
            (
                {},
                set(),
            ),
            (
                {"item": TestItem},
                set(),  # there must be no stats as ItemProvider is not enabled
            ),
        ),
    )
    @inlineCallbacks
    def test_stats(self, cb_args, expected, injector):
        def callback_factory():
            args = ", ".join([f"{k}: {v.__name__}" for k, v in cb_args.items()])
            exec(f"def callback(response: DummyResponse, {args}): pass")
            return locals().get("callback")

        callback = callback_factory()
        response = get_response_for_testing(callback)
        _ = yield from injector.build_callback_dependencies(response.request, response)
        prefix = "poet/injector/"
        poet_stats = {
            name.replace(prefix, ""): value
            for name, value in injector.crawler.stats.get_stats().items()
            if name.startswith(prefix)
        }
        assert set(poet_stats) == expected

    @inlineCallbacks
    def test_po_provided_via_item(self, injector):
        rules = [ApplyRule(Patterns(include=()), use=TestItemPage, to_return=TestItem)]
        registry = RulesRegistry(rules=rules)
        providers = {"scrapy_poet.page_input_providers.ItemProvider": 10}
        injector = get_injector_for_testing(providers, registry=registry)

        def callback(response: DummyResponse, item: TestItem):
            pass

        response = get_response_for_testing(callback)
        _ = yield from injector.build_callback_dependencies(response.request, response)
        key = "poet/injector/tests.test_injection.TestItemPage"
        assert key in set(injector.crawler.stats.get_stats())


class TestInjectorOverrides:
    @pytest.mark.parametrize("override_should_happen", [True, False])
    @inlineCallbacks
    def test_overrides(self, providers, override_should_happen):
        domain = "example.com" if override_should_happen else "other-example.com"
        # The request domain is example.com, so overrides shouldn't be applied
        # when we configure them for domain other-example.com
        rules = [
            ApplyRule(Patterns([domain]), use=PriceInDollarsPO, instead_of=PricePO),
            ApplyRule(
                Patterns([domain]), use=OtherEurDollarRate, instead_of=EurDollarRate
            ),
        ]
        registry = RulesRegistry(rules=rules)
        injector = get_injector_for_testing(providers, registry=registry)

        def callback(
            response: DummyResponse, price_po: PricePO, rate_po: EurDollarRate
        ):
            pass

        response = get_response_for_testing(callback)
        kwargs = yield from injector.build_callback_dependencies(
            response.request, response
        )
        kwargs_types = {key: type(value) for key, value in kwargs.items()}
        price_po = kwargs["price_po"]
        item = price_po.to_item()

        if override_should_happen:
            assert kwargs_types == {
                "price_po": PriceInDollarsPO,
                "rate_po": OtherEurDollarRate,
            }
            # Note that OtherEurDollarRate don't have effect inside PriceInDollarsPO
            # because composability of overrides is forbidden
            assert item == {"price": 22 * 1.1, "currency": "$"}
        else:
            assert kwargs_types == {"price_po": PricePO, "rate_po": EurDollarRate}
            assert item == {"price": 22, "currency": "€"}


def test_load_provider_classes():
    provider_as_string = (
        f"{HttpResponseProvider.__module__}.{HttpResponseProvider.__name__}"
    )
    injector = get_injector_for_testing(
        {provider_as_string: 2, HttpResponseProvider: 1}
    )
    assert all(type(prov) is HttpResponseProvider for prov in injector.providers)
    assert len(injector.providers) == 2


def test_check_all_providers_are_callable():
    check_all_providers_are_callable([HttpResponseProvider(None)])
    with pytest.raises(NonCallableProviderError) as exinf:
        check_all_providers_are_callable(
            [PageObjectInputProvider(None), HttpResponseProvider(None)]
        )

    assert "PageObjectInputProvider" in str(exinf.value)
    assert "not callable" in str(exinf.value)


def test_is_class_provided_by_any_provider_fn():
    providers = [
        get_provider({str}),
        get_provider(lambda x: issubclass(x, InjectionError)),
        get_provider(frozenset({int, float})),
    ]
    is_provided = is_class_provided_by_any_provider_fn(providers)
    is_provided_empty = is_class_provided_by_any_provider_fn([])

    for cls in [str, InjectionError, NonCallableProviderError, int, float]:
        assert is_provided(cls)
        assert not is_provided_empty(cls)

    for cls in [bytes, Exception]:
        assert not is_provided(cls)
        assert not is_provided_empty(cls)

    class WrongProvider(PageObjectInputProvider):
        provided_classes = [str]  # Lists are not allowed, only sets or funcs

    with pytest.raises(InjectionError):
        is_class_provided_by_any_provider_fn([WrongProvider])


def get_provider_for_cache(classes, a_name, content=None, error=ValueError):
    class Provider(PageObjectInputProvider):
        name = a_name
        provided_classes = classes
        require_response = False

        def __init__(self, crawler):
            self.crawler = crawler

        def __call__(self, to_provide, request: Request):
            domain = get_domain(request.url)
            if not domain == "example.com":
                raise error(
                    f"Domain ({domain}) of URL ({request.url}) is not example.com"
                )
            return [cls(content) if content else cls() for cls in classes]

    return Provider


@pytest.mark.parametrize("cache_errors", [True, False])
@inlineCallbacks
def test_cache(tmp_path, cache_errors):
    """
    In a first run, the cache is empty, and two requests are done, one with exception.
    In the second run we should get the same result as in the first run. The
    behaviour for exceptions vary if caching errors is disabled.
    """

    def validate_instances(instances):
        assert instances[Price].price == "price1"
        assert instances[Name].name == "name1"

    providers = {
        get_provider_for_cache({Price}, "price", content="price1"): 1,
        get_provider_for_cache({Name}, "name", content="name1"): 2,
    }

    cache = tmp_path / "cache"
    if cache.exists():
        print(f"Cache folder {cache} already exists. Weird. Deleting")
        shutil.rmtree(cache)
    settings = {"SCRAPY_POET_CACHE": cache, "SCRAPY_POET_CACHE_ERRORS": cache_errors}
    injector = get_injector_for_testing(providers, settings)

    def callback(response: DummyResponse, arg_price: Price, arg_name: Name):
        pass

    response = get_response_for_testing(callback)
    plan = injector.build_plan(response.request)
    instances = yield from injector.build_instances_from_providers(
        response.request, response, plan
    )
    assert cache.exists()

    validate_instances(instances)

    # Changing the request URL below would result in the following error:
    #   <twisted.python.failure.Failure builtins.ValueError: The URL is not from
    #   example.com>>
    response.request = Request.replace(response.request, url="http://willfail.page")
    with pytest.raises(ValueError):
        plan = injector.build_plan(response.request)
        instances = yield from injector.build_instances_from_providers(
            response.request, response, plan
        )

    # Different providers. They return a different result, but the cache data should prevail.
    providers = {
        get_provider_for_cache({Price}, "price", content="price2", error=KeyError): 1,
        get_provider_for_cache({Name}, "name", content="name2", error=KeyError): 2,
    }
    injector = get_injector_for_testing(providers, settings)

    response = get_response_for_testing(callback)
    plan = injector.build_plan(response.request)
    instances = yield from injector.build_instances_from_providers(
        response.request, response, plan
    )

    validate_instances(instances)

    # If caching errors is disabled, then KeyError should be raised.
    Error = ValueError if cache_errors else KeyError
    response.request = Request.replace(response.request, url="http://willfail.page")
    with pytest.raises(Error):
        plan = injector.build_plan(response.request)
        instances = yield from injector.build_instances_from_providers(
            response.request, response, plan
        )
