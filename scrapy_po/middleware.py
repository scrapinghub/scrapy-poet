# -*- coding: utf-8 -*-
import andi
from twisted.internet.defer import inlineCallbacks, returnValue, maybeDeferred
from scrapy import Request

from .webpage import PageObject
from .utils import get_callback
from .page_input_providers import providers


def is_page_object(argument_type) -> bool:
    return issubclass(argument_type, PageObject)


class InjectPageObjectsMiddleware:
    """
    This downloader middleware instantiates all PageObject subclasses declared
    as request callback arguments. If an argument is not annotated
    as PageObject, this middleware doesn't populate request.cb_kwargs
    for this argument.

    XXX: should it really be a downloader middleware?
    XXX: can this middleware allow to skip downloading
    a page if it is not needed?
    """
    @inlineCallbacks
    def process_response(self, request: Request, response, spider):
        # find out which arguments need to be created
        callback = get_callback(request, spider)
        kwargs_to_provide = andi.to_provide(callback,
                                            can_provide=is_page_object)

        # create WebPage objects and pass them to the callback
        for argname, cls in kwargs_to_provide.items():
            page = yield create_page_object(cls, response)
            request.cb_kwargs[argname] = page

        raise returnValue(response)


@inlineCallbacks
def create_page_object(page_cls, response, dependency_graph=None):
    """
    Create PageObject instances, resolving all constructor dependencies.
    """
    # find out what resources are available
    provider_funcs = {cls: provider(response)
                      for cls, provider in providers.items()}

    def can_provide(cls):
        return cls in provider_funcs or is_page_object(cls)

    # find out which arguments page object needs.
    arguments = andi.inspect(page_cls.__init__)
    kwargs_to_provide = andi.to_provide(arguments, can_provide=can_provide)
    not_supported = arguments.keys() - kwargs_to_provide.keys()
    if not_supported:
        raise TypeError("Can't instantiate arguments: %s" % not_supported)

    # instantiate all arguments
    kwargs = {}
    dependency_graph = dependency_graph or []
    for argname, cls in kwargs_to_provide.items():
        if cls in dependency_graph:
            raise TypeError("Cyclic dependency found. Dependency graph: %s ",
                            " -> ".join(map(str, dependency_graph + [cls])))
        if cls in provider_funcs:
            provider = provider_funcs[cls]
            kwargs[argname] = yield maybeDeferred(provider)
        else:
            page = yield create_page_object(cls, response, dependency_graph + [cls])
            kwargs[argname] = page

    # create and return WebPage object
    page = page_cls(**kwargs)
    raise returnValue(page)
