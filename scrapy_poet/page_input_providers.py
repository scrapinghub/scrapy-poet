"""The Injection Middleware needs a standard way to build the Page Inputs dependencies
that the Page Objects uses to get external data (e.g. the HTML). That's why we
have created a colletion of Page Object Input Providers.

The current module implements a Page Input Provider for
:class:`web_poet.HttpResponse <web_poet.page_inputs.http.HttpResponse>`, which
is in charge of providing the response HTML from Scrapy. You could also implement
different providers in order to acquire data from multiple external sources,
for example, from scrapy-playwright or from an API for automatic extraction.
"""
from typing import Any, Callable, ClassVar, FrozenSet, List, Set, Union
from warnings import warn

from scrapy import Request
from scrapy.crawler import Crawler
from scrapy.http import Response
from web_poet import (
    HttpClient,
    HttpRequest,
    HttpRequestHeaders,
    HttpResponse,
    HttpResponseHeaders,
    PageParams,
    RequestUrl,
    ResponseUrl,
    Stats,
)
from web_poet.page_inputs.stats import StatCollector, StatNum

from scrapy_poet.downloader import create_scrapy_downloader
from scrapy_poet.injection_errors import MalformedProvidedClassesError


class PageObjectInputProvider:
    """
    This is the base class for creating Page Object Input Providers.

    A Page Object Input Provider (POIP) takes responsibility for providing
    instances of some types to Scrapy callbacks. The types a POIP provides must
    be declared in the class attribute ``provided_classes``.

    POIPs are initialized when the spider starts by invoking the ``__init__`` method,
    which receives the ``scrapy_poet.injection.Injector`` instance as argument.

    The ``__call__`` method must be overridden, and it is inside this method
    where the actual instances must be build. The default ``__call__`` signature
    is as follows:

    .. code-block:: python

        def __call__(self, to_provide: Set[Callable]) -> Sequence[Any]:

    Therefore, it receives a list of types to be provided and return a list
    with the instances created (don't get confused by the
    ``Callable`` annotation. Think on it as a synonym of ``Type``).

    Additional dependencies can be declared in the ``__call__`` signature
    that will be automatically injected. Currently, scrapy-poet is able
    to inject instances of the following classes:

    - :class:`~scrapy.http.Request`
    - :class:`~scrapy.http.Response`
    - :class:`~scrapy.crawler.Crawler`
    - :class:`~scrapy.settings.Settings`
    - :class:`~scrapy.statscollectors.StatsCollector`

    Finally, ``__call__`` function can execute asynchronous code. Just
    either prepend the declaration with ``async`` to use futures or annotate it with
    ``@inlineCallbacks`` for deferred execution. Additionally, you
    might want to configure Scrapy ``TWISTED_REACTOR`` to support ``asyncio``
    libraries.

    The available POIPs should be declared in the spider setting using the key
    ``SCRAPY_POET_PROVIDERS``. It must be a dictionary that follows same
    structure than the
    :ref:`Scrapy Middlewares <scrapy:topics-downloader-middleware-ref>`
    configuration dictionaries.

    A simple example of a provider:

    .. code-block:: python

        class BodyHtml(str): pass

        class BodyHtmlProvider(PageObjectInputProvider):
            provided_classes = {BodyHtml}

            def __call__(self, to_provide, response: Response):
                return [BodyHtml(response.css("html body").get())]

    The **provided_classes** class attribute is the ``set`` of classes
    that this provider provides.
    Alternatively, it can be a function with type ``Callable[[Callable], bool]`` that
    returns ``True`` if and only if the given type, which must be callable,
    is provided by this provider.
    """

    provided_classes: Union[Set[Callable], Callable[[Callable], bool]]
    name: ClassVar[str] = ""  # It must be a unique name. Used by the cache mechanism

    def is_provided(self, type_: Callable) -> bool:
        """
        Return ``True`` if the given type is provided by this provider based
        on the value of the attribute ``provided_classes``
        """
        if isinstance(self.provided_classes, (Set, FrozenSet)):
            return type_ in self.provided_classes
        elif callable(self.provided_classes):
            return self.provided_classes(type_)
        else:
            raise MalformedProvidedClassesError(
                f"Unexpected type {type_!r} for 'provided_classes' attribute of"
                f"{self!r}. Expected either 'set' or 'callable'"
            )

    # FIXME: Can't import the Injector as class annotation due to circular dep.
    def __init__(self, injector):
        """Initializes the provider. Invoked only at spider start up."""
        self.injector = injector

    # Remember that is expected for all children to implement the ``__call__``
    # method. The simplest signature for it is:
    #
    #   def __call__(self, to_provide: Set[Callable]) -> Sequence[Any]:
    #
    # But some adding some other injectable attributes are possible
    # (see the class docstring)
    #
    # The technical reason why this method was not declared abstract is that
    # injection breaks the method overriding rules and mypy then complains.


class HttpRequestProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.HttpRequest
    <web_poet.page_inputs.http.HttpRequest>` instances.
    """

    provided_classes = {HttpRequest}
    name = "request_data"

    def __call__(self, to_provide: Set[Callable], request: Request):
        """Builds a :class:`web_poet.HttpRequest
        <web_poet.page_inputs.http.HttpRequest>` instance using a
        :class:`scrapy.http.Request` instance.
        """
        return [
            HttpRequest(
                url=RequestUrl(request.url),
                method=request.method,
                headers=HttpRequestHeaders.from_bytes_dict(request.headers),
                body=request.body,
            )
        ]


class HttpResponseProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.HttpResponse
    <web_poet.page_inputs.http.HttpResponse>` instances.
    """

    provided_classes = {HttpResponse}
    name = "response_data"

    def __call__(self, to_provide: Set[Callable], response: Response):
        """Builds a :class:`web_poet.HttpResponse
        <web_poet.page_inputs.http.HttpResponse>` instance using a
        :class:`scrapy.http.Response` instance.
        """
        return [
            HttpResponse(
                url=response.url,
                body=response.body,
                status=response.status,
                headers=HttpResponseHeaders.from_bytes_dict(response.headers),
            )
        ]


class HttpClientProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.HttpClient
    <web_poet.page_inputs.client.HttpClient>` instances.
    """

    provided_classes = {HttpClient}

    def __call__(self, to_provide: Set[Callable], crawler: Crawler):
        """Creates an :class:`web_poet.HttpClient
        <web_poet.page_inputs.client.HttpClient>` instance using Scrapy's
        downloader.
        """
        downloader = create_scrapy_downloader(crawler.engine.download)
        save_responses = crawler.settings.getbool("_SCRAPY_POET_SAVEFIXTURE")
        return [
            HttpClient(request_downloader=downloader, save_responses=save_responses)
        ]


class PageParamsProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.PageParams
    <web_poet.page_inputs.page_params.PageParams>` instances.
    """

    provided_classes = {PageParams}

    def __call__(self, to_provide: Set[Callable], request: Request):
        """Creates a :class:`web_poet.PageParams
        <web_poet.page_inputs.page_params.PageParams>` instance based on the
        data found from the ``meta["page_params"]`` field of a
        :class:`scrapy.http.Response` instance.
        """
        return [PageParams(request.meta.get("page_params", {}))]


class RequestUrlProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.RequestUrl
    <web_poet.page_inputs.http.RequestUrl>` instances.
    """

    provided_classes = {RequestUrl}
    name = "request_url"

    def __call__(self, to_provide: Set[Callable], request: Request):
        """Builds a :class:`web_poet.RequestUrl <web_poet.page_inputs.http.RequestUrl>`
        instance using :class:`scrapy.Request <scrapy.http.Request>` instance.
        """
        return [RequestUrl(url=request.url)]


class ResponseUrlProvider(PageObjectInputProvider):
    provided_classes = {ResponseUrl}
    name = "response_url"

    def __call__(self, to_provide: Set[Callable], response: Response):
        """Builds a :class:`web_poet.RequestUrl <web_poet.page_inputs.http.RequestUrl>`
        instance using a :class:`scrapy.http.Response` instance.
        """
        return [ResponseUrl(url=response.url)]


class ItemProvider(PageObjectInputProvider):
    provided_classes = set()
    name = "item"

    def __init__(self, injector):
        super().__init__(injector)
        msg = "The ItemProvider now does nothing and you should disable it."
        warn(msg, DeprecationWarning, stacklevel=2)

    async def __call__(
        self,
        to_provide: Set[Callable],
        request: Request,
        response: Response,
    ) -> List[Any]:
        return []


class ScrapyPoetStatCollector(StatCollector):
    def __init__(self, stats):
        self._stats = stats
        self._prefix = "poet/stats/"

    def set(self, key: str, value: Any) -> None:  # noqa: D102
        self._stats.set_value(f"{self._prefix}{key}", value)

    def inc(self, key: str, value: StatNum = 1) -> None:  # noqa: D102
        self._stats.inc_value(f"{self._prefix}{key}", value)


class StatsProvider(PageObjectInputProvider):
    """This class provides :class:`web_poet.Stats
    <web_poet.page_inputs.client.Stats>` instances.
    """

    provided_classes = {Stats}

    def __call__(self, to_provide: Set[Callable], crawler: Crawler):
        """Creates an :class:`web_poet.Stats
        <web_poet.page_inputs.client.Stats>` instance using Scrapy's
        stat collector.
        """

        return [Stats(stat_collector=ScrapyPoetStatCollector(crawler.stats))]
