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
from dataclasses import make_dataclass
from inspect import isclass
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Type,
    Union,
)
from weakref import WeakKeyDictionary

import andi
import attr
from scrapy import Request
from scrapy.crawler import Crawler
from scrapy.http import Response
from web_poet import (
    HttpClient,
    HttpResponse,
    HttpResponseHeaders,
    ItemPage,
    PageParams,
    RequestUrl,
    ResponseUrl,
)
from web_poet.fields import item_from_fields_sync
from web_poet.pages import is_injectable
from web_poet.utils import ensure_awaitable

from scrapy_poet.downloader import create_scrapy_downloader
from scrapy_poet.injection_errors import (
    MalformedProvidedClassesError,
    ProviderDependencyDeadlockError,
)
from scrapy_poet.utils import _normalize_annotated_cls, _pick_fields


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
        if isinstance(self.provided_classes, Set):
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

    def __init__(self, crawler: Crawler):
        if hasattr(crawler, "request_fingerprinter"):

            def fingerprint(x):
                return crawler.request_fingerprinter.fingerprint(x).hex()

            self._fingerprint = fingerprint
        else:
            from scrapy.utils.request import request_fingerprint

            self._fingerprint = request_fingerprint

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
        _request = request.replace(callback=None, errback=None)
        request_data = {
            k: str(v) for k, v in _request.to_dict().items() if k in request_keys
        }
        fp_data = {
            "SCRAPY_FINGERPRINT": self._fingerprint(_request),
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

    def __init__(self, injector):
        super().__init__(injector)
        self.registry = self.injector.registry

        # The key that's used here is the ``scrapy.Request`` instance to ensure
        # that the cached instances under it are properly garbage collected
        # after processing such request.
        self._cached_instances = WeakKeyDictionary()

    def provided_classes(self, cls):
        """If the item is in any of the ``to_return`` in the rules, then it can
        definitely provide by using the corresponding page object in ``use``.
        """
        cls = _normalize_annotated_cls(cls)
        return isclass(cls) and self.registry.search(to_return=cls)

    def update_cache(self, request: Request, mapping: Dict[Type, Any]) -> None:
        if request not in self._cached_instances:
            self._cached_instances[request] = {}
        self._cached_instances[request].update(mapping)

    def get_from_cache(self, request: Request, cls: Callable) -> Optional[Any]:
        return self._cached_instances.get(request, {}).get(cls)

    async def __call__(
        self,
        to_provide: Set[Callable],
        request: Request,
        response: Response,
    ) -> List[Any]:
        results = []
        for raw_cls in to_provide:
            cls = _normalize_annotated_cls(raw_cls)

            item = self.get_from_cache(request, cls)
            if item:
                results.append(item)
                continue

            page_object_cls = self.registry.page_cls_for_item(request.url, cls)
            if not page_object_cls:
                continue

            # https://github.com/scrapinghub/andi/issues/23#issuecomment-1331682180
            fake_call_signature = make_dataclass(
                "FakeCallSignature", [("page_object", page_object_cls)]
            )
            plan = andi.plan(
                fake_call_signature,
                is_injectable=is_injectable,
                externally_provided=self.injector.is_class_provided_by_any_provider,
            )

            try:
                po_instances = await self.injector.build_instances(
                    request, response, plan
                )
            except RecursionError:
                raise ProviderDependencyDeadlockError(
                    f"Deadlock detected! A loop has been detected to trying to "
                    f"resolve this plan: {plan}"
                )

            page_object = po_instances[page_object_cls]
            item = await self._produce_item(page_object, raw_cls)

            self.update_cache(request, po_instances)
            self.update_cache(request, {type(item): item})

            results.append(item)
        return results

    async def _produce_item(self, page_object: ItemPage, cls_or_annotated: Any) -> Any:
        field_names = _pick_fields(cls_or_annotated)
        if field_names:
            item_dict = item_from_fields_sync(
                page_object, item_cls=dict, skip_nonitem_fields=False
            )
            item_cls = _normalize_annotated_cls(cls_or_annotated)
            item = item_cls(
                **{
                    name: await ensure_awaitable(item_dict[name])
                    for name in item_dict
                    if name in field_names
                }
            )
            return item

        return await page_object.to_item()
