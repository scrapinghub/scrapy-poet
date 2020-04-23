import abc

from typing import Type

from core_po.objects import Injectable
from core_po.responses import HTMLResponse
from scrapy.http.response import Response

# FIXME: refactor _providers / provides / register,  make a nicer API
providers = {}


class InjectableProvider(abc.ABC):
    """Represents a ``InjectableProvider`` interface.

    Providers are used to build dependencies used by ``core_po.Injectables``.
    """

    @abc.abstractmethod
    def __call__(self):
        """Builds and returns a ``PageObject`` dependency."""
        pass


def register(provider: Type[InjectableProvider], cls: Type[Injectable]):
    """Register a ``InjectableProvider`` for a given ``core_po.Injectable``.

    Providers are fetched by our custom Downloader Middleware when it's
    building callback arguments and their dependencies.
    """
    providers[cls] = provider


def provides(cls):
    """Decorates a ``InjectableProvider`` registering it as a provider."""

    def decorator(provider):
        register(provider, cls)
        return provider

    return decorator


@provides(HTMLResponse)
class HTMLResponseProvider(InjectableProvider):
    """Provides a ``core_po.HTMLResponse`` based on a ``scrapy.http.Response``
    object.
    """

    def __init__(self, response: Response):
        """Receives a ``scrapy.http.Response`` as a dependency."""
        self.response = response

    def __call__(self) -> HTMLResponse:
        """Uses the ``scrapy.http.Response`` to build an instance of a
        ``core_po.HTMLResponse``.
        """
        return HTMLResponse(
            url=self.response.url,
            content=self.response.text
        )
