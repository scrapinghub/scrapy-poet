"""The Injection Middleware needs a standard way to build dependencies for
the Page Inputs used by the request callbacks. That's why we have created a
repository of ``PageObjectInputProvider`` subclasses.

You could implement different providers in order to acquire data from multiple
external sources, for example, Splash or Auto Extract API.
"""
import typing

from scrapy_poet import autoextract
from scrapy_poet.page_input_providers import (
    PageObjectInputProvider,
    ResponseDataProvider,
)
# FIXME: refactor _providers / provides / register,  make a nicer API

providers = {}


def register(provider_class: typing.Type[PageObjectInputProvider],
             provided_class: typing.Optional[typing.Type] = None):
    """This method registers a Page Object Input Provider in the providers
    registry. It could be replaced by the use of the ``provides`` decorator.

    If ``provided_class`` is not specified, we get it from ``provider_class``.

    Examples:

        register(ResponseDataProvider)
        register(ResponseDataProvider, ResponseData)
    """
    if provided_class is None:
        provided_class = provider_class.provided_class

    providers[provided_class] = provider_class


# TODO: does this decorator still make sense?
def provides(provided_class: typing.Type):
    """This decorator could be used with classes that inherits from
    ``PageObjectInputProvider`` in order to automatically register them as
    providers.

    See ``ResponseDataProvider``'s implementation for an example.
    """
    def decorator(provider_class: typing.Type[PageObjectInputProvider]):
        register(provider_class, provided_class)
        return provider_class

    return decorator


register(ResponseDataProvider)
register(autoextract.ArticleResponseDataProvider)
register(autoextract.ProductResponseDataProvider)
