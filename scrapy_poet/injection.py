import inspect
import logging
import os
import pprint
import warnings
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

import andi
from andi.typeutils import issubclass_safe
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.settings import Settings
from scrapy.statscollectors import StatsCollector
from scrapy.utils.conf import build_component_list
from scrapy.utils.defer import maybeDeferred_coro
from scrapy.utils.misc import load_object
from twisted.internet.defer import inlineCallbacks
from web_poet import RulesRegistry
from web_poet.pages import is_injectable

from scrapy_poet.api import _CALLBACK_FOR_MARKER, DummyResponse
from scrapy_poet.cache import SqlitedictCache
from scrapy_poet.injection_errors import (
    InjectionError,
    NonCallableProviderError,
    UndeclaredProvidedTypeError,
)
from scrapy_poet.page_input_providers import PageObjectInputProvider
from scrapy_poet.utils import is_min_scrapy_version

from .utils import create_registry_instance, get_scrapy_data_path

logger = logging.getLogger(__name__)


class Injector:
    """
    Keep all the logic required to do dependency injection in Scrapy callbacks.
    Initializes the providers from the spider settings at initialization.
    """

    def __init__(
        self,
        crawler: Crawler,
        *,
        default_providers: Optional[Mapping] = None,
        registry: Optional[RulesRegistry] = None,
    ):
        self.crawler = crawler
        self.spider = crawler.spider
        self.registry = registry or RulesRegistry()
        self.load_providers(default_providers)
        self.init_cache()

    def load_providers(self, default_providers: Optional[Mapping] = None):  # noqa: D102
        providers_dict = {
            **(default_providers or {}),
            **self.crawler.settings.getdict("SCRAPY_POET_PROVIDERS"),
        }
        provider_classes = build_component_list(providers_dict)
        logger.info(f"Loading providers:\n {pprint.pformat(provider_classes)}")
        self.providers = [load_object(cls)(self) for cls in provider_classes]
        check_all_providers_are_callable(self.providers)
        # Caching whether each provider requires the scrapy response
        self.is_provider_requiring_scrapy_response = {
            provider: is_provider_requiring_scrapy_response(provider)
            for provider in self.providers
        }
        # Caching the function for faster execution
        self.is_class_provided_by_any_provider = is_class_provided_by_any_provider_fn(
            self.providers
        )

    def close(self) -> None:  # noqa: D102
        if self.cache:
            self.cache.close()

    def init_cache(self):  # noqa: D102
        self.cache = None
        cache_filename = self.crawler.settings.get("SCRAPY_POET_CACHE")
        if cache_filename and isinstance(cache_filename, bool):
            cache_filename = os.path.join(
                get_scrapy_data_path(createdir=True), "scrapy-poet-cache.sqlite3"
            )
        if cache_filename:
            compressed = self.crawler.settings.getbool("SCRAPY_POET_CACHE_GZIP", True)
            self.caching_errors = self.crawler.settings.getbool(
                "SCRAPY_POET_CACHE_ERRORS", False
            )
            self.cache = SqlitedictCache(cache_filename, compressed=compressed)
            logger.info(
                f"Cache enabled. File: {cache_filename!r}. Compressed: {compressed}. Caching errors: {self.caching_errors}"
            )

    def available_dependencies_for_providers(
        self, request: Request, response: Response
    ):  # noqa: D102
        deps = {
            Crawler: self.crawler,
            Spider: self.spider,
            Settings: self.crawler.settings,
            StatsCollector: self.crawler.stats,
            Request: request,
            Response: response,
        }
        assert deps.keys() == SCRAPY_PROVIDED_CLASSES
        return deps

    def discover_callback_providers(
        self, request: Request
    ) -> Set[PageObjectInputProvider]:
        """Discover the providers that are required to fulfil the callback dependencies"""
        plan = self.build_plan(request)
        result = set()
        for cls, _ in plan:
            for provider in self.providers:
                if provider.is_provided(cls):
                    result.add(provider)

        return result

    def is_scrapy_response_required(self, request: Request):
        """
        Check whether Scrapy's :class:`~scrapy.http.Request`'s
        :class:`~scrapy.http.Response` is going to be used.
        """
        callback = get_callback(request, self.spider)
        if is_callback_requiring_scrapy_response(callback, request.callback):
            return True

        for provider in self.discover_callback_providers(request):
            if self.is_provider_requiring_scrapy_response[provider]:
                return True

        return False

    def build_plan(self, request: Request) -> andi.Plan:
        """Create a plan for building the dependencies required by the callback"""
        callback = get_callback(request, self.spider)
        return andi.plan(
            callback,
            is_injectable=is_injectable,
            externally_provided=self.is_class_provided_by_any_provider,
            # Ignore the type since andi.plan expects overrides to be
            # Callable[[Callable], Optional[Callable]] but the registry
            # returns the typing for ``dict.get()`` method.
            overrides=self.registry.overrides_for(request.url).get,  # type: ignore[arg-type]
        )

    @inlineCallbacks
    def build_instances(self, request: Request, response: Response, plan: andi.Plan):
        """Build the instances dict from a plan including external dependencies."""
        # First we build the external dependencies using the providers
        instances = yield from self.build_instances_from_providers(
            request, response, plan
        )
        # All the remaining dependencies are internal so they can be built just
        # following the andi plan.
        for cls, kwargs_spec in plan.dependencies:
            if cls not in instances.keys():
                instances[cls] = cls(**kwargs_spec.kwargs(instances))

        return instances

    @inlineCallbacks
    def build_instances_from_providers(
        self, request: Request, response: Response, plan: andi.Plan
    ):
        """Build dependencies handled by registered providers"""
        instances: Dict[Callable, Any] = {}
        scrapy_provided_dependencies = self.available_dependencies_for_providers(
            request, response
        )
        dependencies_set = {cls for cls, _ in plan.dependencies}
        for provider in self.providers:
            provided_classes = {
                cls for cls in dependencies_set if provider.is_provided(cls)
            }
            provided_classes -= instances.keys()  # ignore already provided types
            if not provided_classes:
                continue

            objs, fingerprint = None, None
            cache_hit = False
            if self.cache and provider.has_cache_support:
                if not provider.name:
                    raise NotImplementedError(
                        f"The provider {type(provider)} must have a `name` defined if"
                        f" you want to use the cache. It must be unique across the providers."
                    )
                # Return the data if it is already in the cache
                fingerprint = f"{provider.name}_{provider.fingerprint(set(provided_classes), request)}"
                try:
                    data = self.cache[fingerprint]
                except KeyError:
                    self.crawler.stats.inc_value("scrapy-poet/cache/miss")
                else:
                    self.crawler.stats.inc_value("scrapy-poet/cache/hit")
                    if isinstance(data, Exception):
                        raise data
                    objs = provider.deserialize(data)
                    cache_hit = True

            if not objs:
                kwargs = andi.plan(
                    provider,
                    is_injectable=is_injectable,
                    externally_provided=scrapy_provided_dependencies,
                    full_final_kwargs=False,
                ).final_kwargs(scrapy_provided_dependencies)
                try:

                    # Invoke the provider to get the data
                    objs = yield maybeDeferred_coro(
                        provider, set(provided_classes), **kwargs
                    )

                except Exception as e:
                    if (
                        self.cache
                        and self.caching_errors
                        and provider.has_cache_support
                    ):
                        # Save errors in the cache
                        self.cache[fingerprint] = e
                        self.crawler.stats.inc_value("scrapy-poet/cache/firsthand")
                    raise

            objs_by_type: Dict[Callable, Any] = {type(obj): obj for obj in objs}
            extra_classes = objs_by_type.keys() - provided_classes
            if extra_classes:
                raise UndeclaredProvidedTypeError(
                    f"{provider} has returned instances of types {extra_classes} "
                    "that are not among the declared supported classes in the "
                    f"provider: {provider.provided_classes}"
                )
            instances.update(objs_by_type)

            if self.cache and not cache_hit and provider.has_cache_support:
                # Save the results in the cache
                self.cache[fingerprint] = provider.serialize(objs)
                self.crawler.stats.inc_value("scrapy-poet/cache/firsthand")

        return instances

    @inlineCallbacks
    def build_callback_dependencies(self, request: Request, response: Response):
        """
        Scan the configured callback for this request looking for the
        dependencies and build the corresponding instances. Return a kwargs
        dictionary with the built instances.
        """
        plan = self.build_plan(request)
        provider_instances = yield from self.build_instances(request, response, plan)
        return plan.final_kwargs(provider_instances)


def check_all_providers_are_callable(providers):
    for provider in providers:
        if not callable(provider):
            raise NonCallableProviderError(
                f"The provider {type(provider)} is not callable. "
                f"It must implement '__call__' method"
            )


def is_class_provided_by_any_provider_fn(
    providers: List[PageObjectInputProvider],
) -> Callable[[Callable], bool]:
    """
    Return a function of type ``Callable[[Type], bool]`` that return
    True if the given type is provided by any of the registered providers.

    The attribute ``provided_classes`` from each provided is used.
    This attribute can be a :class:`set` or a ``Callable``. All sets are
    joined together for efficiency.
    """
    sets_of_types: Set[Callable] = set()  # caching all sets found
    individual_is_callable: List[Callable[[Callable], bool]] = [
        sets_of_types.__contains__
    ]
    for provider in providers:
        provided_classes = provider.provided_classes

        if isinstance(provided_classes, (Set, frozenset)):
            sets_of_types.update(provided_classes)
        elif callable(provider.provided_classes):
            individual_is_callable.append(provided_classes)
        else:
            raise InjectionError(
                f"Unexpected type '{type(provided_classes)}' for "
                f"'{type(provider)}.provided_classes'. Expected either 'set' "
                f"or 'callable'"
            )

    def is_provided_fn(type: Callable) -> bool:
        for is_provided in individual_is_callable:
            if is_provided(type):
                return True
        return False

    return is_provided_fn


def get_callback(request, spider):
    """Get the :attr:`scrapy.Request.callback <scrapy.http.Request.callback>` of
    a :class:`scrapy.Request <scrapy.http.Request>`.
    """
    if request.callback is None:
        return getattr(spider, "parse")  # noqa: B009
    return request.callback


_unset = object()


def is_callback_requiring_scrapy_response(
    callback: Callable, raw_callback: Any = _unset
) -> bool:
    """
    Check whether the request's callback method requires the response.
    Basically, it won't be required if the response argument in the
    callback is annotated with :class:`~.DummyResponse`.
    """
    if getattr(callback, _CALLBACK_FOR_MARKER, False) is True:
        # The callback_for function was used to create this callback.
        return False

    signature = inspect.signature(callback)
    first_parameter_key = next(iter(signature.parameters))
    first_parameter = signature.parameters[first_parameter_key]
    if str(first_parameter).startswith("*"):
        # Parse method is probably using *args and **kwargs annotation.
        # Let's assume response is going to be used.
        return True

    if first_parameter.annotation is first_parameter.empty:
        # There's no type annotation, so we're probably using response here.
        return True

    if issubclass_safe(first_parameter.annotation, DummyResponse):
        # See: https://github.com/scrapinghub/scrapy-poet/issues/48
        # See: https://github.com/scrapinghub/scrapy-poet/issues/118
        if raw_callback is None and not is_min_scrapy_version("2.8.0"):
            warnings.warn(
                "A request has been encountered with callback=None which "
                "defaults to the parse() method. If the parse() method is "
                "annotated with scrapy_poet.DummyResponse (or its subclasses), "
                "we're assuming this isn't intended and would simply ignore "
                "this annotation.\n\n"
                "See the Pitfalls doc for more info."
            )
            return True

        # Type annotation is DummyResponse, so we're probably NOT using it.
        return False

    # Type annotation is not DummyResponse, so we're probably using it.
    return True


SCRAPY_PROVIDED_CLASSES = {
    Spider,
    Request,
    Response,
    Crawler,
    Settings,
    StatsCollector,
}


def is_provider_requiring_scrapy_response(provider):
    """Check whether injectable provider makes use of a valid
    :class:`scrapy.http.Response`.
    """
    plan = andi.plan(
        provider.__call__,
        is_injectable=is_injectable,
        externally_provided=SCRAPY_PROVIDED_CLASSES,
    )
    for possible_type, _ in plan.dependencies:
        if issubclass(possible_type, Response):
            return True

    return False


def get_injector_for_testing(
    providers: Mapping,
    additional_settings: Optional[Dict] = None,
    registry: Optional[RulesRegistry] = None,
) -> Injector:
    """
    Return an :class:`Injector` using a fake crawler.
    Useful for testing providers
    """

    class MySpider(Spider):
        name = "my_spider"

    settings = Settings(
        {**(additional_settings or {}), "SCRAPY_POET_PROVIDERS": providers}
    )
    crawler = Crawler(MySpider)
    crawler.settings = settings
    spider = MySpider()
    spider.settings = settings
    crawler.spider = spider
    if not registry:
        registry = create_registry_instance(RulesRegistry, crawler)
    return Injector(crawler, registry=registry)


def get_response_for_testing(callback: Callable) -> Response:
    """
    Return a :class:`scrapy.http.Response` with fake content with the configured
    callback. It is useful for testing providers.
    """
    url = "http://example.com"
    html = """
        <html>
            <body>
                <div class="breadcrumbs">
                    <a href="/food">Food</a> /
                    <a href="/food/sweets">Sweets</a>
                </div>
                <h1 class="name">Chocolate</h1>
                <p>Price: <span class="price">22€</span></p>
                <p class="description">The best chocolate ever</p>
            </body>
        </html>
        """.encode(
        "utf-8"
    )
    request = Request(url, callback=callback)
    response = Response(url, 200, None, html, request=request)
    return response
