# -*- coding: utf-8 -*-
from typing import Dict, Callable, Type, Any, Tuple, Generator

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
        plan, provider_instances = build_plan(callback, response)

        # Build all instances declared as dependencies
        instances = yield from build_instances(
            plan.dependencies, provider_instances)

        # Fill the callback arguments with the created instances
        for argname, cls in plan.final_arguments.items():
            # Precedence of user callback arguments
            if argname not in request.cb_kwargs:
                request.cb_kwargs[argname] = instances[cls]
            # TODO: check if all arguments are fulfilled somehow?

        raise returnValue(response)


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


@inlineCallbacks
def build_instances(plan: andi.Plan, providers):
    """ Build the instances dict from a plan """
    instances = {}
    for cls, params in plan:
        if cls in providers:
            instances[cls] = yield maybeDeferred(providers[cls])
        else:
            kwargs = {param: instances[pcls]
                      for param, pcls in params.items()}
            instances[cls] = cls(**kwargs)
    raise returnValue(instances)


def build_providers(response) -> Dict[Type, Callable]:
    # find out what resources are available
    return {cls: provider(response)
            for cls, provider in providers.items()}


def is_injectable(argument_type: Type) -> bool:
    """
    A type is injectable if inherits from ``Injectable``. None is also injectable
    by default.
    """
    return (argument_type == type(None) or
            issubclass(argument_type, Injectable))
