# -*- coding: utf-8 -*-
import inspect
from typing import Dict, Callable, Type, Tuple

from scrapy.utils.defer import maybeDeferred_coro

import andi
from twisted.internet.defer import inlineCallbacks, returnValue
from scrapy import Request
from scrapy.http import Response, TextResponse

from .webpage import Injectable
from .utils import get_callback, DummyResponse
from.page_inputs import ResponseData
from .page_input_providers import providers


class InjectionMiddleware:
    """
    This downloader middleware instantiates all Injectable subclasses declared
    as request callback arguments and any other parameter with a provider
    for its type. Otherwise this middleware doesn't populate request.cb_kwargs
    for this argument.

    XXX: should it really be a downloader middleware?
    """
    def is_response_going_to_be_used(self, request, spider):
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

    def process_request(self, request: Request, spider):
        """Check if the request is needed and if the download can be skipped.

        Here we try to infer if the request's response is going to be used
        by its designated parser or an injected Page Object.

        If we evaluate that the request could be ignored, we return a
        DummyResponse object linked to the original Request instance.

        With this behavior we're able to optimize spider executions avoid
        having to download URLs twice or when they're not needed, for example,
        when a Page Object relies only on a third-party API like AutoExtract.
        """
        if self.is_response_going_to_be_used(request, spider):
            return

        spider.logger.debug(f'Skipping download of {request}')
        return DummyResponse(url=request.url, request=request)

    @inlineCallbacks
    def process_response(self, request: Request, response, spider):
        # find out the dependencies
        callback = get_callback(request, spider)
        plan, provider_instances = build_plan(callback, response)

        # Build all instances declared as dependencies
        instances = yield from build_instances(
            plan.dependencies, provider_instances)

        # Fill the callback arguments with the created instances
        for arg, value in plan.final_kwargs(instances).items():
            # Precedence of user callback arguments
            if arg not in request.cb_kwargs:
                request.cb_kwargs[arg] = value
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
    for cls, kwargs_spec in plan:
        if cls in providers:
            instances[cls] = yield maybeDeferred_coro(providers[cls])
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    raise returnValue(instances)


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
