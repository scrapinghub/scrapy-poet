import abc

from core_po.objects import PageObject
from core_po.responses import HTMLResponse
from scrapy.http.response import Response

# FIXME: refactor _providers / provides / register,  make a nicer API
providers = {}


class PageObjectProvider(abc.ABC):
    """Represents a ``PageObjectProvider`` interface.

    Providers are used to build dependencies used by ``core_po.PageObjects``.
    """

    @abc.abstractmethod
    def __call__(self):
        """Builds and returns a ``PageObject`` dependency."""
        pass


def register(provider: type(PageObjectProvider), cls: type(PageObject)):
    """Register a ``PageObjectProvider`` for a given ``core_po.PageObject``.

    Providers are fetched by our custom Downloader Middleware when it's
    building callback arguments and their dependencies.
    """
    providers[cls] = provider


def provides(cls):
    """Decorates a ``PageObjectProvider`` registering it as a provider."""

    def decorator(provider):
        register(provider, cls)
        return provider

    return decorator


@provides(HTMLResponse)
class HTMLResponseProvider(PageObjectProvider):
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
