# -*- coding: utf-8 -*-
import inspect
from typing import Tuple, Dict, Type, Callable

import andi
from scrapy.http import Response
from scrapy.utils.defer import maybeDeferred_coro
from twisted.internet.defer import inlineCallbacks, returnValue

from scrapy_po.webpage import Injectable
from scrapy_po.page_input_providers import providers


def get_callback(request, spider):
    """Get request.callback of a scrapy.Request, as a callable."""
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback


class DummyResponse(Response):

    def __init__(self, url, request=None):
        super(DummyResponse, self).__init__(url=url, request=request)


def is_callback_using_response(callback: Callable):
    """Check whether the request's callback method is going to use response."""
    spec = inspect.getfullargspec(callback)
    try:
        arg_name = spec.args[1]  # first index is self, second is response
    except IndexError:
        # Parse method is probably using *args and **kwargs annotation.
        # Let's assume response is going to be used.
        return True

    if arg_name not in spec.annotations:
        # There's no type annotation, so we're probably using response here.
        return True

    if issubclass(spec.annotations[arg_name], DummyResponse):
        # Type annotation is DummyResponse, so we're probably NOT using it.
        return False

    # Type annotation is not DummyResponse, so we're probably using it.
    return True


def is_provider_using_response(provider):
    """Check whether injectable provider makes use of a valid Response."""
    spec = inspect.getfullargspec(provider)
    for cls in spec.annotations.values():
        if not issubclass(cls, Response):
            # Type annotation is not a sub-class of Response.
            continue

        if issubclass(cls, DummyResponse):
            # Type annotation is a DummyResponse.
            continue

        # Type annotation is a sub-class of Response, but not a sub-class
        # of DummyResponse, so we're probably using it.
        return True

    # Could not find any Response type annotation in the used providers.
    return False


def is_response_going_to_be_used(request, spider):
    """Check whether the request's response is going to be used."""
    callback = get_callback(request, spider)
    if is_callback_using_response(callback):
        return True

    plan, _ = build_plan(callback, None)
    for provider in get_providers(plan):
        if is_provider_using_response(provider):
            return True

    return False


def get_providers(plan: andi.Plan):
    for obj, _ in plan:
        provider = providers.get(obj)
        if not provider:
            continue

        yield provider


def build_plan(callback, response
               ) -> Tuple[andi.Plan, Dict[Type, Callable]]:
    """Build a plan for the injection in the callback."""
    provider_instances = build_providers(response)
    plan = andi.plan(
        callback,
        is_injectable=is_injectable,
        externally_provided=provider_instances.keys()
    )
    return plan, provider_instances


def build_providers(response) -> Dict[Type, Callable]:
    # find out what resources are available
    result = {}
    for cls, provider in providers.items():
        spec = inspect.getfullargspec(provider)
        if spec.args:
            result[cls] = provider(response)
        else:
            result[cls] = provider()

    return result


def is_injectable(argument_type: Callable) -> bool:
    """A type is injectable if inherits from ``Injectable``."""
    return (isinstance(argument_type, type) and
            issubclass(argument_type, Injectable))


@inlineCallbacks
def build_instances(plan: andi.Plan, providers):
    """Build the instances dict from a plan."""
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in providers:
            instances[cls] = yield maybeDeferred_coro(providers[cls])
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    raise returnValue(instances)
