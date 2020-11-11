import inspect
from typing import Dict, Callable, Any, List, Set

from twisted.internet.defer import inlineCallbacks, returnValue

import andi
from scrapy import Request, Spider
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.settings import Settings
from scrapy.statscollectors import StatsCollector
from scrapy.utils.defer import maybeDeferred_coro
from scrapy.utils.misc import load_object
from scrapy_poet.injection_errors import (UndeclaredProvidedTypeError,
                                          NonCallableProviderError,
                                          InjectionError)
from scrapy_poet.page_input_providers import PageObjectInputProvider, PROVIDERS
from scrapy_poet.api import _CALLBACK_FOR_MARKER, DummyResponse
from web_poet.pages import is_injectable


class Injector:
    """
    Keep all the logic required to do dependency injection in Scrapy callbacks.
    Initializes the providers from the spider settings at initialization.
    """
    def __init__(self, crawler: Crawler):
        self.crawler = crawler
        self.spider = crawler.spider
        self.load_providers()

    def load_providers(self):
        self.providers = [
            cls(self.crawler)
            for cls in load_provider_classes(self.spider.settings)
        ]
        check_all_providers_are_callable(self.providers)
        # Caching whether each provider requires the scrapy response
        self.is_provider_requiring_scrapy_response = {
            id(provider): is_provider_requiring_scrapy_response(provider)
            for provider in self.providers
        }
        # Caching the function for faster execution
        self.is_class_provided_by_any_provider = \
            is_class_provided_by_any_provider_fn(self.providers)

    def available_dependencies_for_providers(self,
                                             request: Request,
                                             response: Response):
        deps = {
            Crawler: self.crawler,
            Spider: self.spider,
            Settings: self.spider.settings,
            StatsCollector: self.crawler.stats,
            Request: request,
            Response: response,
        }
        assert deps.keys() == SCRAPY_PROVIDED_CLASSES
        return deps

    def discover_callback_providers(self, callback: Callable
                                    ) -> Set[PageObjectInputProvider]:
        """Discover which providers are required to fulfil the callback dependencies"""
        plan = andi.plan(
            callback,
            is_injectable=is_injectable,
            externally_provided=self.is_class_provided_by_any_provider,
        )
        result = set()
        for cls, _ in plan:
            for provider in self.providers:
                if provider.is_provided(cls):
                    result.add(provider)

        return result

    def is_scrapy_response_required(self, request: Request):
        """
        Check whether the request's response is going to be used.
        """
        callback = get_callback(request, self.spider)
        if is_callback_requiring_scrapy_response(callback):
            return True

        for provider in self.discover_callback_providers(callback):
            if self.is_provider_requiring_scrapy_response[id(provider)]:
                return True

        return False

    def build_plan(self, request: Request) -> andi.Plan:
        """Build a plan for building the dependencies required by the callback"""
        callback = get_callback(request, self.spider)
        return andi.plan(
            callback,
            is_injectable=is_injectable,
            externally_provided=self.is_class_provided_by_any_provider,
        )

    @inlineCallbacks
    def build_instances(
            self, request: Request, response: Response, plan: andi.Plan):
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

        raise returnValue(instances)

    @inlineCallbacks
    def build_instances_from_providers(
            self, request: Request, response: Response, plan: andi.Plan):
        """"Build dependencies handled by registered providers"""
        instances: Dict[Callable, Any] = {}
        scrapy_provided_dependencies = self.available_dependencies_for_providers(
            request, response)
        dependencies_set = {cls for cls, _ in plan.dependencies}
        for provider in self.providers:
            provided_classes = {cls for cls in dependencies_set if
                                provider.is_provided(cls)}
            provided_classes -= instances.keys()  # ignore already provided types
            if not provided_classes:
                continue

            kwargs = andi.plan(
                provider,
                is_injectable=is_injectable,
                externally_provided=scrapy_provided_dependencies,
                full_final_kwargs=False,
            ).final_kwargs(scrapy_provided_dependencies)
            results = yield maybeDeferred_coro(provider, set(provided_classes),
                                               **kwargs)
            extra_classes = results.keys() - provided_classes
            if extra_classes:
                raise UndeclaredProvidedTypeError(
                    f"{provider} has returned {extra_classes} but they're not "
                    f"listed as provided classes {provider.provided_classes}"
                )
            instances.update(results)

        raise returnValue(instances)

    @inlineCallbacks
    def build_callback_dependencies(self, request: Request, response: Response):
        """
        Scan the configured callback for this request looking for the
        dependencies and build the corresponding instances. Return a kwargs
        dictionary with the built instances.
        """
        plan = self.build_plan(request)
        provider_instances = yield from self.build_instances(request, response, plan)
        callback_kwargs = plan.final_kwargs(provider_instances)
        raise returnValue(callback_kwargs)


def check_all_providers_are_callable(providers):
    for provider in providers:
        if not callable(provider):
            raise NonCallableProviderError(
                f"The provider {type(provider)} is not callable. "
                f"It must implement '__call__' method"
            )


def load_provider_classes(settings: Settings) -> List[PageObjectInputProvider]:
    result = []
    for cls in settings.getlist('SCRAPY_POET_PROVIDER_CLASSES') or PROVIDERS:
        if not callable(cls):
            cls = load_object(cls)

        result.append(cls)

    return result


def is_class_provided_by_any_provider_fn(providers: List[PageObjectInputProvider]
                                         ) -> Callable[[Callable], bool]:
    """
    Return a function of type ``Callable[[Type], bool]`` that return
    True if the given type is provided by any of the registered providers.

    The attribute ``provided_classes`` from each provided is used.
    This attribute can be a ``set`` or a ``Callable``. All sets are
    joined together for efficiency.
    """
    sets_of_types: Set[Callable] = set()  # caching all sets found
    individual_is_callable: List[Callable[[Callable], bool]] = [sets_of_types.__contains__]
    for provider in providers:
        provided_classes = provider.provided_classes

        if isinstance(provided_classes, Set):
            sets_of_types.update(provided_classes)
        elif callable(provider.provided_classes):
            individual_is_callable.append(provided_classes)
        else:
            raise InjectionError(
                f"Unexpected type '{type(provided_classes)}' for "
                f"'{type(provider)}.provided_classes'. Expected either 'set' "
                f"or 'callable'")

    def is_provided_fn(type: Callable) -> bool:
        for is_provided in individual_is_callable:
            if is_provided(type):
                return True
        return False

    return is_provided_fn


def get_callback(request, spider):
    """Get request.callback of a scrapy.Request, as a callable."""
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback


def is_callback_requiring_scrapy_response(callback: Callable):
    """
    Check whether the request's callback method requires the response.
    Basically, it won't be required if the response argument in the
    callback is annotated with ``DummyResponse``
    """
    if getattr(callback, _CALLBACK_FOR_MARKER, False) is True:
        # The callback_for function was used to create this callback.
        return False

    signature = inspect.signature(callback)
    first_parameter_key = next(iter(signature.parameters))
    first_parameter = signature.parameters[first_parameter_key]
    if str(first_parameter).startswith('*'):
        # Parse method is probably using *args and **kwargs annotation.
        # Let's assume response is going to be used.
        return True

    if first_parameter.annotation is first_parameter.empty:
        # There's no type annotation, so we're probably using response here.
        return True

    if issubclass(first_parameter.annotation, DummyResponse):
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
    """Check whether injectable provider makes use of a valid Response."""
    plan = andi.plan(
        provider.__call__,
        is_injectable=is_injectable,
        externally_provided=SCRAPY_PROVIDED_CLASSES,
    )
    for possible_type, _ in plan.dependencies:
        if issubclass(possible_type, Response):
            return True

    return False