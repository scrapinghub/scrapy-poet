"""The Injection Middleware needs a standard way to build dependencies for
the Page Inputs used by the request callbacks. That's why we have created a
repository of ``PageObjectInputProvider`` subclasses.

You could implement different providers in order to acquire data from multiple
external sources, for example, Splash or Auto Extract API.
"""
import typing

from scrapy_poet import autoextract
from scrapy_poet.providers import (
    PageObjectInputProvider,
    ResponseDataProvider,
)
# FIXME: refactor _providers / provides / register,  make a nicer API

providers = {}


def register(provider_class: typing.Type[PageObjectInputProvider]):
    """This method registers a Page Object Input Provider in the providers
    registry.

    It could be replaced by the use of the ``provides`` decorator but you need
    to make sure the module containing those classes are imported during
    runtime.
    """
    providers[provider_class.provided_class] = provider_class


# TODO: does this decorator still make sense?
def provider(cls: typing.Type[PageObjectInputProvider]):
    """This decorator could be used with classes that inherits from
    ``PageObjectInputProvider`` in order to automatically register them as
    providers.

    See ``ResponseDataProvider``'s implementation for an example.
    """
    register(cls)
    return cls


register(ResponseDataProvider)
register(autoextract.ArticleResponseDataProvider)
register(autoextract.ProductResponseDataProvider)
