import functools
import inspect
import logging
import os
import pprint
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Type,
    cast,
    get_type_hints,
)
from weakref import WeakKeyDictionary

import andi
from andi.typeutils import issubclass_safe, strip_annotated
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector, StatsCollector
from scrapy.utils.conf import build_component_list
from scrapy.utils.defer import deferred_from_coro, maybeDeferred_coro
from scrapy.utils.misc import load_object
from twisted.internet.defer import inlineCallbacks
from web_poet import RulesRegistry
from web_poet.annotated import AnnotatedInstance
from web_poet.page_inputs.http import request_fingerprint
from web_poet.pages import ItemPage, is_injectable
from web_poet.serialization.api import deserialize_leaf, load_class, serialize
from web_poet.utils import get_fq_class_name

from scrapy_poet.api import _CALLBACK_FOR_MARKER, DummyResponse
from scrapy_poet.cache import SerializedDataCache
from scrapy_poet.injection_errors import (
    NonCallableProviderError,
    UndeclaredProvidedTypeError,
)
from scrapy_poet.page_input_providers import PageObjectInputProvider
from scrapy_poet.utils import is_min_scrapy_version

from .utils import create_registry_instance, get_scrapy_data_path

logger = logging.getLogger(__name__)


class _UNDEFINED:
    pass


class DynamicDeps(dict):
    """A container for dynamic dependencies provided via the ``"inject"`` request meta key.

    The dynamic dependency instances are available at the run time as dict
    values with keys being dependency types.
    """

    pass


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

    def init_cache(self):  # noqa: D102
        self.cache = {}
        cache_path = self.crawler.settings.get("SCRAPY_POET_CACHE")

        # SCRAPY_POET_CACHE: True
        if cache_path and isinstance(cache_path, bool):
            cache_path = os.path.join(
                get_scrapy_data_path(createdir=True), "scrapy-poet-cache"
            )

        # SCRAPY_POET_CACHE: <cache_path>
        if cache_path:
            self.cache = SerializedDataCache(cache_path)
            self.caching_errors = self.crawler.settings.getbool(
                "SCRAPY_POET_CACHE_ERRORS", False
            )
            logger.info(
                f"Cache enabled. Folder: {cache_path!r}. Caching errors: {self.caching_errors}"
            )

        # This is different from the cache above as it only stores instances as long
        # as the request exists. This is useful for latter providers to re-use the
        # already built instances by earlier providers.
        self.weak_cache: WeakKeyDictionary[Request, Dict] = WeakKeyDictionary()

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
            custom_builder_fn=self._get_custom_builder(request),
        )

    def _get_custom_builder(
        self, request: Request
    ) -> Callable[[Callable], Optional[Callable]]:
        """Return a function suitable for passing as ``custom_builder_fn`` to ``andi.plan``.

        The returned function can map an item to a factory for that item based
        on the registry and also supports filling :class:`.DynamicDeps`.
        """

        @functools.lru_cache(maxsize=None)  # to minimize the registry queries
        def mapping_fn(dep_cls: Callable) -> Optional[Callable]:
            # building DynamicDeps
            if dep_cls is DynamicDeps:
                dynamic_types = request.meta.get("inject", [])
                if not dynamic_types:
                    return lambda: {}
                return self._get_dynamic_deps_factory(dynamic_types)

            # building items from pages
            page_object_cls: Optional[Type[ItemPage]] = self.registry.page_cls_for_item(
                request.url, cast(type, dep_cls)
            )
            if not page_object_cls:
                return None

            async def item_factory(page: page_object_cls) -> dep_cls:  # type: ignore[valid-type]
                return await page.to_item()  # type: ignore[attr-defined]

            return item_factory

        return mapping_fn

    @staticmethod
    def _get_dynamic_deps_factory_text(
        type_names: Iterable[str],
    ) -> str:
        # inspired by Python 3.11 dataclasses._create_fn()
        # https://github.com/python/cpython/blob/v3.11.9/Lib/dataclasses.py#L413
        args = [f"{name}_arg: {name}" for name in type_names]
        args_str = ", ".join(args)
        result_args = [f"strip_annotated({name}): {name}_arg" for name in type_names]
        result_args_str = ", ".join(result_args)
        create_args_str = ", ".join(type_names)
        return (
            f"def __create_fn__({create_args_str}):\n"
            f" def dynamic_deps_factory({args_str}) -> DynamicDeps:\n"
            f"  return DynamicDeps({{{result_args_str}}})\n"
            f" return dynamic_deps_factory"
        )

    @staticmethod
    def _get_dynamic_deps_factory(
        dynamic_types: List[type],
    ) -> Callable[..., DynamicDeps]:
        """Return a function that creates a :class:`.DynamicDeps` instance from its args.

        It takes instances of types from ``dynamic_types`` as args and returns
        a :class:`.DynamicDeps` instance where keys are types and values are
        corresponding args. It has correct type hints so that it can be used as
        an ``andi`` custom builder.
        """
        type_names: List[str] = []
        for type_ in dynamic_types:
            type_ = cast(type, strip_annotated(type_))
            if not isinstance(type_, type):
                raise TypeError(f"Expected a dynamic dependency type, got {type_!r}")
            type_names.append(type_.__name__)
        txt = Injector._get_dynamic_deps_factory_text(type_names)
        ns: Dict[str, Any] = {}
        exec(txt, globals(), ns)
        return ns["__create_fn__"](*dynamic_types)

    @inlineCallbacks
    def build_instances(
        self,
        request: Request,
        response: Response,
        plan: andi.Plan,
    ):
        """Build the instances dict from a plan including external dependencies."""
        # First we build the external dependencies using the providers
        instances = yield from self.build_instances_from_providers(
            request,
            response,
            plan,
        )
        # All the remaining dependencies are internal so they can be built just
        # following the andi plan.
        assert self.crawler.stats
        for cls, kwargs_spec in plan.dependencies:
            if cls not in instances.keys():
                result_cls: type = cast(type, cls)
                if isinstance(cls, andi.CustomBuilder):
                    result_cls = cls.result_class_or_fn
                    instances[result_cls] = yield deferred_from_coro(
                        cls.factory(**kwargs_spec.kwargs(instances))
                    )
                else:
                    instances[result_cls] = cls(**kwargs_spec.kwargs(instances))
                cls_fqn = get_fq_class_name(result_cls)
                self.crawler.stats.inc_value(f"poet/injector/{cls_fqn}")

        return instances

    @inlineCallbacks
    def build_instances_from_providers(
        self,
        request: Request,
        response: Response,
        plan: andi.Plan,
    ):
        """Build dependencies handled by registered providers"""
        assert self.crawler.stats
        instances: Dict[Callable, Any] = {}
        scrapy_provided_dependencies = self.available_dependencies_for_providers(
            request, response
        )
        dependencies_set = {cls for cls, _ in plan.dependencies}
        objs: List[Any]
        for provider in self.providers:
            provided_classes = {
                cls for cls in dependencies_set if provider.is_provided(cls)
            }
            provided_classes -= instances.keys()  # ignore already provided types

            if not provided_classes:
                continue

            objs, fingerprint = [], None
            cache_hit = False
            if self.cache:
                if not provider.name:
                    raise NotImplementedError(
                        f"The provider {type(provider)} must have a `name` defined if"
                        f" you want to use the cache. It must be unique across the providers."
                    )
                # This one should take `web_poet.HttpRequest` but `scrapy.Request` will work as well
                # TODO: add `scrapy.Request` type in request_fingerprint() annotations
                fingerprint = f"{provider.name}_{request_fingerprint(request)}"  # type: ignore[arg-type]
                # Return the data if it is already in the cache
                try:
                    data = self.cache[fingerprint].items()
                except KeyError:
                    self.crawler.stats.inc_value("poet/cache/miss")
                else:
                    self.crawler.stats.inc_value("poet/cache/hit")
                    if isinstance(data, Exception):
                        raise data
                    objs = [
                        deserialize_leaf(
                            load_class(dep_type_name), serialized_leaf_data
                        )
                        for dep_type_name, serialized_leaf_data in data
                    ]
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
                    if self.cache and self.caching_errors:
                        # Save errors in the cache
                        self.cache[fingerprint] = e
                        self.crawler.stats.inc_value("poet/cache/firsthand")
                    raise

            objs_by_type: Dict[Callable, Any] = {}
            for obj in objs:
                if isinstance(obj, AnnotatedInstance):
                    cls = obj.get_annotated_cls()
                    obj = obj.result
                else:
                    cls = type(obj)
                objs_by_type[cls] = obj
            extra_classes = objs_by_type.keys() - provided_classes
            if extra_classes:
                raise UndeclaredProvidedTypeError(
                    f"{provider} has returned instances of types {extra_classes} "
                    "that are not among the declared supported classes in the "
                    f"provider: {provided_classes}"
                )
            instances.update(objs_by_type)

            if self.weak_cache.get(request):
                self.weak_cache[request].update(objs_by_type)
            else:
                self.weak_cache[request] = objs_by_type

            if self.cache and not cache_hit:
                # Save the results in the cache
                self.cache[fingerprint] = serialize(objs)
                self.crawler.stats.inc_value("poet/cache/firsthand")

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

    The ``is_provided`` method from each provider is used.
    """
    callables: List[Callable[[Callable], bool]] = []
    for provider in providers:
        callables.append(provider.is_provided)

    def is_provided_fn(type_: Callable) -> bool:
        for is_provided in callables:
            if is_provided(type_):
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

    callback_type_hints = get_type_hints(callback)
    first_parameter_type_hint = callback_type_hints.get(first_parameter_key, _UNDEFINED)
    if first_parameter_type_hint is _UNDEFINED:
        # There's no type annotation, so we're probably using response here.
        return True

    if issubclass_safe(first_parameter_type_hint, DummyResponse):
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
    crawler = Crawler(MySpider, settings)
    crawler.spider = MySpider.from_crawler(crawler)
    crawler.stats = MemoryStatsCollector(crawler)
    if not registry:
        registry = create_registry_instance(RulesRegistry, crawler)
    return Injector(crawler, registry=registry)


def get_response_for_testing(
    callback: Callable, meta: Optional[Dict[str, Any]] = None
) -> Response:
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
    request = Request(url, callback=callback, meta=meta)
    response = Response(url, 200, None, html, request=request)
    return response
