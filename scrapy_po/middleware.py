# -*- coding: utf-8 -*-
from typing import Dict, Callable

import andi
from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred
from scrapy import Request

from .webpage import Injectable
from .utils import get_callback
from .page_input_providers import providers


class InjectionMiddleware:
    """
    This downloader middleware instantiates all Injectable subclasses declared
    as request callback arguments and any other parameter with a provider
    for its type. Otherwise this middleware doesn't populate request.cb_kwargs
    for this argument.

    XXX: should it really be a downloader middleware?
    XXX: can this middleware allow to skip downloading
    a page if it is not needed?
    """
    @inlineCallbacks
    def process_response(self, request: Request, response, spider):
        # find out the dependencies
        callback = get_callback(request, spider)
        providers = build_providers(response)
        can_provide = can_provide_fn(providers)
        plan = andi.plan(callback, can_provide,
                         providers.__contains__)

        # Build all instances declared as dependencies
        instances = {}
        for cls, params in plan.items():
            if cls in providers:
                instances[cls] = yield maybeDeferred(providers[cls])
            elif cls == andi.FunctionArguments:
                pass
            else:
                kwargs = {param: instances[pcls]
                          for param, pcls in params.items()}
                instances[cls] = cls(**kwargs)

        # Fill the callback arguments with the created instances
        for argname, cls in plan[andi.FunctionArguments].items():
            if argname not in request.cb_kwargs:
                request.cb_kwargs[argname] = instances[cls]
            # TODO: check if all arguments are fulfilled somehow?

        raise returnValue(response)


def build_providers(response) -> Dict[type, Callable]:
    # find out what resources are available
    return {cls: provider(response)
            for cls, provider in providers.items()}


def can_provide_fn(providers):
    """ A type is providable if it is ``Injectable`` or if there exists
    a provider for it. Also None is providable by default. """
    def fn(argument_type):
        return (argument_type == type(None) or
                argument_type in providers or
                issubclass(argument_type, Injectable))
    return fn
