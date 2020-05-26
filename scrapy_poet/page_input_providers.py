"""The Injection Middleware needs a standard way to build dependencies for
the Page Inputs used by the request callbacks. That's why we have created a
repository of ``PageObjectInputProviders``.

You could implement different providers in order to acquire data from multiple
external sources, for example, Splash or Auto Extract API.
"""
import abc
import typing

from scrapy.http import Response
from web_poet.page_inputs import ResponseData

# FIXME: refactor _providers / provides / register,  make a nicer API
providers = {}


class PageObjectInputProvider(abc.ABC):
    """This is an abstract class for describing Page Object Input Providers."""

    def __init__(self):
        """You can override this method to receive external dependencies."""

    @abc.abstractmethod
    def __call__(self):
        """This method is responsible for building Page Input dependencies."""


def register(provider_class: typing.Type[PageObjectInputProvider],
             provided_class: typing.Type):
    """This method registers a Page Object Input Provider in the providers
    registry. It could be replaced by the use of the ``provides`` decorator.

    Example:

        register(ResponseDataProvider, ResponseData)
    """
    providers[provided_class] = provider_class


def provides(provided_class: typing.Type):
    """This decorator should be used with classes that inherits from
    ``PageObjectInputProvider`` in order to automatically register them as
    providers.

    See ``ResponseDataProvider``'s implementation for an example.
    """
    def decorator(provider_class: typing.Type[PageObjectInputProvider]):
        register(provider_class, provided_class)
        return provider_class

    return decorator


@provides(ResponseData)
class ResponseDataProvider(PageObjectInputProvider):
    """This class provides ``web_poet.page_inputs.ResponseData`` instances."""

    def __init__(self, response: Response):
        """This class receives a Scrapy ``Response`` as a dependency."""
        self.response = response

    def __call__(self):
        """This method builds a ``ResponseData`` instance using a Scrapy
        ``Response``.
        """
        return ResponseData(
            url=self.response.url,
            html=self.response.text
        )
