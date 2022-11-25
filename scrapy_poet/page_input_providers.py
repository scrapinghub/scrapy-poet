"""The Injection Middleware needs a standard way to build the Page Inputs dependencies
that the Page Objects uses to get external data (e.g. the HTML). That's why we
have created a repository of ``PageObjectInputProviders``.

The current module implements a ``PageObjectInputProviders`` for
:class:`web_poet.page_inputs.HttpResponse`, which is in charge of providing the response
HTML from Scrapy. You could also implement different providers in order to
acquire data from multiple external sources, for example,
Splash or Auto Extract API.
"""
import abc
import json
from inspect import isclass
from typing import Any, Callable, ClassVar, List, Optional, Sequence, Set, Union

import attr
from scrapy import Request
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.utils.request import request_fingerprint
from web_poet import (
    HttpClient,
    HttpResponse,
    HttpResponseHeaders,
    PageParams,
    RequestUrl,
    ResponseUrl,
)

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

    provided_classes: ClassVar[Union[Set[Callable], Callable[[Callable], bool]]]
    name: ClassVar[str] = ""  # It must be a unique name. Used by the cache mechanism

    def is_provided(self, type_: Callable) -> bool:
        """
        Return ``True`` if the given type is provided by this provider based
        on the value of the attribute ``provided_classes``
        """
        if isinstance(self.provided_classes, Set):
            return type_ in self.provided_classes
        elif callable(self.provided_classes):
            return self.provided_classes(type_)
        else:
            raise MalformedProvidedClassesError(
                f"Unexpected type '{type_}' for 'provided_classes' attribute of "
                f"'{self}.'. Expected either 'set' or 'callable'"
            )

    def requirements_for(self, cls, request) -> Optional[List[Any]]:
        """For a provider to work, there might be some additional requirements
        that it needs from its side.

        Subclasses should override this method to return such requirements.

        ``cls`` contains the class that the provider needs to provide.

        ``request`` could provide additional context.
        """
        pass

    # TODO: andi could be enhanced to avoid this workaround of declaring a
    # dynamic call signature.
    def dynamic_call_signature(self, provided_classes, request):
        """Return a function with the call signature to be used instead of
        ``__call__()``.

        Subclasses should override this if the dependencies they declare in
        the ``__call__()`` are dynamic.

        For example, declaring the dependencies via type annotations wouldn't
        work when the provider needs to provide for a wide variety of classes.

        When this is overridden, the Injector detects it and uses it instead of
        the ``__call__()`` method when deriving the ``andi.Plan``.
        """
        pass

    # FIXME: Can't import the class annotation due to circular dep.
    def __init__(self, injector):
        """Initializes the provider. Invoked only at spider start up."""
        pass

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


class CacheDataProviderMixin(abc.ABC):
    """Providers that intend to support the ``SCRAPY_POET_CACHE`` should inherit
    from this mixin class.
    """

    @abc.abstractmethod
    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        """
        Return a fingerprint that identifies this particular request. It will be used to implement
        the cache and record/replay mechanism
        """
        pass

    @abc.abstractmethod
    def serialize(self, result: Sequence[Any]) -> Any:
        """
        Serializes the results of this provider. The data returned will be pickled.
        """
        pass

    @abc.abstractmethod
    def deserialize(self, data: Any) -> Sequence[Any]:
        """
        Deserialize some results of the provider that were previously serialized using the method
        :meth:`serialize`.
        """
        pass

    @property
    def has_cache_support(self):
        return True


class HttpResponseProvider(PageObjectInputProvider, CacheDataProviderMixin):
    """This class provides ``web_poet.page_inputs.HttpResponse`` instances."""

    provided_classes = {HttpResponse}
    name = "response_data"

    def __call__(self, to_provide: Set[Callable], response: Response):
        """Builds a ``HttpResponse`` instance using a Scrapy ``Response``"""
        return [
            HttpResponse(
                url=response.url,
                body=response.body,
                status=response.status,
                headers=HttpResponseHeaders.from_bytes_dict(response.headers),
            )
        ]

    def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
        request_keys = {"url", "method", "body"}
        request_data = {
            k: str(v) for k, v in request.to_dict().items() if k in request_keys
        }
        fp_data = {
            "SCRAPY_FINGERPRINT": request_fingerprint(request),
            **request_data,
        }
        return json.dumps(fp_data, ensure_ascii=False, sort_keys=True)

    def serialize(self, result: Sequence[Any]) -> Any:
        return [attr.asdict(response_data) for response_data in result]

    def deserialize(self, data: Any) -> Sequence[Any]:
        return [
            HttpResponse(
                response_data["url"],
                response_data["body"],
                status=response_data["status"],
                headers=response_data["headers"],
                encoding=response_data["_encoding"],
            )
            for response_data in data
        ]


class HttpClientProvider(PageObjectInputProvider):
    """This class provides ``web_poet.requests.HttpClient`` instances."""

    provided_classes = {HttpClient}

    def __call__(self, to_provide: Set[Callable], crawler: Crawler):
        """Creates an ``web_poet.requests.HttpClient`` instance using Scrapy's
        downloader.
        """
        downloader = create_scrapy_downloader(crawler.engine.download)
        return [HttpClient(request_downloader=downloader)]


class PageParamsProvider(PageObjectInputProvider):
    """This class provides ``web_poet.page_inputs.PageParams`` instances."""

    provided_classes = {PageParams}

    def __call__(self, to_provide: Set[Callable], request: Request):
        """Creates a ``web_poet.requests.PageParams`` instance based on the
        data found from the ``meta["page_params"]`` field of a
        ``scrapy.http.Response`` instance.
        """
        return [PageParams(request.meta.get("page_params", {}))]


class RequestUrlProvider(PageObjectInputProvider):
    """This class provides ``web_poet.page_inputs.RequestUrl`` instances."""

    provided_classes = {RequestUrl}
    name = "request_url"

    def __call__(self, to_provide: Set[Callable], request: Request):
        """Builds a ``RequestUrl`` instance using a Scrapy ``Request``."""
        return [RequestUrl(url=request.url)]


class ResponseUrlProvider(PageObjectInputProvider):

    provided_classes = {ResponseUrl}
    name = "response_url"

    def __call__(self, to_provide: Set[Callable], response: Response):
        """Builds a ``ResponseUrl`` instance using a Scrapy ``Response``."""
        return [ResponseUrl(url=response.url)]


class ItemProvider(PageObjectInputProvider):

    name = "item"

    _prefix_po = "_po_"

    def __init__(self, injector):
        self.registry = injector.overrides_registry

    def provided_classes(self, *args, **kwargs):
        """If the item is in any of the ``to_return`` in the rules, then it can
        definitely provide by using the corresponding page object in ``use``.
        """
        cls = args[-1]

        # TODO: The search operation in the registry could be expensive when
        # there are lots of rules. We could cache it up since this method is
        # called multiple times by the ``Injector`` when making dependencies.
        return isclass(cls) and self.registry.search(to_return=cls)

    def requirements_for(self, cls, request) -> Optional[List[Any]]:
        """Return the PO class that is capable of returning the item class
        instance via its ``.to_item()`` method.

        ``request`` provides additional context for matching the URL patterns.
        """
        provider_dependency = self.registry.page_object_for_item(request).get(cls)
        return [provider_dependency]

    def dynamic_call_signature(self, provided_classes, request):
        """This is overridden since we need to accommodate different item classes
        which couldn't be easily declared in the ``__call__()``.
        """

        # provided_class = list(provided_classes)[0]
        # provider_dependency = self.requirements_for(provided_class, request)
        # provider_dependency = provider_dependency[0]

        # # Ignore the typing since it's dynamic and mypy complains.
        # def func(_po_1: provider_dependency):  # type: ignore
            # pass

        # FIXME: support multiple provided_classes

        provider_dependencies = []
        for cls in provided_classes:
            reqs = self.requirements_for(cls, request)
            provider_dependencies.extend(reqs)

            # FIXME: This doesn't produce correct one
            # for r in reqs:
                # if self.provided_classes(r):  # only allow POs
                    # provider_dependencies.append(r)

        # NOTES: This doesn't work since `dep` instance cannot be referred to
        # inside the `exec()`.
        # signature = ""
        # for i, dep in enumerate(provider_dependencies):
            # signature += f"{self._prefix_po}{i}: {dep}"
        # exec("def func(" + signature + "): pass", globals())

        # NOTES: Stopped here; func cannot be returned since it's not existing?

        # TODO: Opt to update andi so we can avoid the following:
        # andi.plan(
        #   provider.dynamic_call_signature(provided_classes, request),
        #   ...

        # TODO: remove this temporary workaround after the following is
        # addressed: https://github.com/scrapinghub/andi/issues/23
        if len(provider_dependencies) == 1:
            def func(_po_0: provider_dependencies[0]):  # type: ignore
                pass
        elif len(provider_dependencies) == 2:
            def func(_po_0: provider_dependencies[0], _po_1: provider_dependencies[1]):  # type: ignore
                pass

        return func

    async def __call__(
        self,
        to_provide: Set[Callable],
        **kwargs,
    ):
        results = []

        # Find the POs passed via kwargs that start with self._prefix_po
        for name in kwargs:
            if not name.startswith(self._prefix_po):
                continue
            item = await kwargs[name].to_item()
            results.append(item)
        return results

        # FIXME: There might be some POs here that have their '.to_item()'
        # method called twice, which could be expensive in terms of ARs. The
        # injector should prevent passing POs that it already has instances
        # with here.

    # FIXME: to_provide isn't used at all in any provider. Could be refactored.
