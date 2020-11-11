import attr
import pytest
from pytest_twisted import inlineCallbacks

from scrapy import Spider, Request
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.settings import Settings
from scrapy_poet import ResponseDataProvider, PageObjectInputProvider, \
    DummyResponse
from scrapy_poet.injection import load_provider_classes, \
    check_all_providers_are_callable, is_class_provided_by_any_provider_fn, \
    Injector
from scrapy_poet.injection_errors import NonCallableProviderError, \
    InjectionError
from web_poet import Injectable


def get_provider(classes):
    class Provider(PageObjectInputProvider):
        provided_classes = classes
        require_response = False

        def __init__(self, crawler):
            self.crawler = crawler

        def __call__(self, to_provide):
            return {cls: cls() for cls in classes}

    return Provider


def get_provider_requiring_response(classes):
    class Provider(PageObjectInputProvider):
        provided_classes = classes
        require_response = True

        def __init__(self, crawler):
            self.crawler = crawler

        def __call__(self, to_provide, response: Response):
            return {cls: cls() for cls in classes}

    return Provider


def get_crawler(settings):
    class MySpider(Spider):
        name = "my_spider"

    crawler = Crawler(MySpider)
    spider = MySpider()
    spider.settings = Settings(settings)
    crawler.spider = spider
    return crawler


@pytest.fixture
def providers():
    return [get_provider_requiring_response({str}),
            get_provider({int, float})]


@pytest.fixture
def injector(providers):
    crawler = get_crawler({"SCRAPY_POET_PROVIDER_CLASSES": providers})
    return Injector(crawler)


@attr.s(auto_attribs=True, cmp=True)
class WrapStr(Injectable):
    a: str


class TestInjector:

    def test_constructor(self, injector):
        assert injector.is_class_provided_by_any_provider(str)
        assert injector.is_class_provided_by_any_provider(float)
        assert not injector.is_class_provided_by_any_provider(bytes)

        for provider in injector.providers:
            assert (injector.is_provider_requiring_scrapy_response[id(provider)] ==
                    provider.require_response)

    def test_non_callable_provider_error(self):
        """Checks that a exception is raised when a provider is not callable"""
        class NonCallableProvider(PageObjectInputProvider):
            pass

        crawler = get_crawler({
            "SCRAPY_POET_PROVIDER_CLASSES": [NonCallableProvider]
        })
        with pytest.raises(NonCallableProviderError):
            Injector(crawler)

    def test_discover_callback_providers(self, injector, providers):
        discover_fn = injector.discover_callback_providers

        def callback_0(a: bytes): pass

        assert set(map(type, discover_fn(callback_0))) == set()

        def callback_1(a: str, b: int): pass

        assert set(map(type, discover_fn(callback_1))) == set(providers)

        def callback_2(a: float, b: int): pass

        assert set(map(type, discover_fn(callback_2))) == {providers[1]}

        def callback_3(a: bytes, b: WrapStr): pass

        assert set(map(type, discover_fn(callback_3))) == {providers[0]}

    def test_is_scrapy_response_required(self, injector):
        request = Request("http://example.com")

        def callback_no_1(response: DummyResponse, a: int): pass

        request.callback = callback_no_1
        assert not injector.is_scrapy_response_required(request)

        def callback_yes_1(response, a: int): pass

        request.callback = callback_yes_1
        assert injector.is_scrapy_response_required(request)

        def callback_yes_2(response: DummyResponse, a: str): pass

        request.callback = callback_yes_2
        assert injector.is_scrapy_response_required(request)

    @inlineCallbacks
    def test_build_instances(self, injector):
        url = "http://example.com"
        request = Request(url)
        response = Response(url, 200, None, b"response")

        def callback(response: DummyResponse, a: int, b: float, c: WrapStr): pass

        request.callback = callback
        plan = injector.build_plan(request)
        instances = yield from injector.build_instances(request, response, plan)
        assert instances == {
            int: int(), float: float(), WrapStr: WrapStr(str()), str: str()
        }



def test_load_provider_classes():
    provider_as_string = f"{ResponseDataProvider.__module__}.{ResponseDataProvider.__name__}"
    settings = Settings({
        "SCRAPY_POET_PROVIDER_CLASSES": [provider_as_string,
                                         ResponseDataProvider]
    })
    assert load_provider_classes(settings) == [ResponseDataProvider] * 2


def test_check_all_providers_are_callable():
    check_all_providers_are_callable([ResponseDataProvider(None)])
    with pytest.raises(NonCallableProviderError) as exinf:
        check_all_providers_are_callable([PageObjectInputProvider(None),
                                          ResponseDataProvider(None)])

    assert "PageObjectInputProvider" in str(exinf.value)
    assert "not callable" in str(exinf.value)

def test_is_class_provided_by_any_provider_fn():
    providers = [get_provider({str}),
                 get_provider(lambda x: issubclass(x, InjectionError)),
                 get_provider({int, float}),
                 ]
    is_provided = is_class_provided_by_any_provider_fn(providers)
    is_provided_empty = is_class_provided_by_any_provider_fn([])

    for cls in [str, InjectionError, NonCallableProviderError, int, float]:
        assert is_provided(cls)
        assert not is_provided_empty(cls)

    for cls in [bytes, Exception]:
        assert not is_provided(cls)
        assert not is_provided_empty(cls)
