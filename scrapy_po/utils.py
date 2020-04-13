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
    """ Get request.callback of a scrapy.Request, as a callable """
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback


class DummyResponse(Response):

    def __init__(self, url, request=None):
        super(DummyResponse, self).__init__(url=url, request=request)


def is_response_going_to_be_used(request, spider):
    """Check whether the request's response is going to be used."""
    callback = get_callback(request, spider)
    plan, _ = build_plan(callback, {})

    for obj, _ in plan:
        spec = inspect.getfullargspec(obj)
        if 'response' not in spec.args:
            # There's not argument named response, let's continue.
            continue

        if 'response' not in spec.annotations:
            # There's no type annotation for the response argument,
            # so we cannot infer that it's not going to be used.
            return True

        if not issubclass(spec.annotations['response'], DummyResponse):
            # The response is not a DummyResponse, so it's probably used.
            return True

    # The parser method is using a DummyResponse as a type annotation.
    # This suggests that the response might not get used.
    # Also, we were not able to find any evidence that the response is
    # going to be used by any injected Page Object.
    return False


def build_plan(callback, response
               ) -> Tuple[andi.Plan, Dict[Type, Callable]]:
    """ Build a plan for the injection in the callback """
    provider_instances = build_providers(response)
    plan = andi.plan(
        callback,
        is_injectable=is_injectable,
        externally_provided=provider_instances.keys()
    )
    return plan, provider_instances


def build_providers(response) -> Dict[Type, Callable]:
    # find out what resources are available
    return {cls: provider(response)
            for cls, provider in providers.items()}


def is_injectable(argument_type: Callable) -> bool:
    """
    A type is injectable if inherits from ``Injectable``.
    """
    return (isinstance(argument_type, type) and
            issubclass(argument_type, Injectable))


@inlineCallbacks
def build_instances(plan: andi.Plan, providers):
    """ Build the instances dict from a plan """
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in providers:
            instances[cls] = yield maybeDeferred_coro(providers[cls])
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    raise returnValue(instances)
