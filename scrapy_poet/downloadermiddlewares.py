"""An important part of scrapy-poet is the Injection Middleware. It's
responsible for injecting Page Input dependencies before the request callbacks
are executed.
"""

from __future__ import annotations

import inspect
import logging
import warnings
from typing import TYPE_CHECKING, Any, TypeVar

from scrapy import Request
from scrapy.downloadermiddlewares.stats import DownloaderStats
from web_poet import HttpRequest, RequestUrl, ResponseUrl, RulesRegistry
from web_poet.exceptions import Retry
from web_poet.pages import is_injectable

from .api import DummyResponse
from .injection import Injector
from .page_input_providers import (
    HttpClientProvider,
    HttpRequestProvider,
    HttpResponseProvider,
    PageParamsProvider,
    RequestUrlProvider,
    ResponseUrlProvider,
    StatsProvider,
)
from .utils import (
    _get_retry_request_from_exception,
    create_registry_instance,
    http_request_to_scrapy_request,
    is_min_scrapy_version,
)

if TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Response

    # typing.Self requires Python 3.11
    from typing_extensions import Self

_T = TypeVar("_T")

# Requests sent via get_page() / get_item() carry this meta key so that
# process_request and process_response skip the normal callback-based
# injection (which get_page/get_item handle themselves).
_POET_PAGE_REQUEST_META_KEY = "_scrapy_poet_page_request"


def _to_scrapy_request(
    request: str | Request | HttpRequest | RequestUrl | ResponseUrl,
) -> Request:
    """Normalise any *RequestLike* value to a fresh :class:`scrapy.Request`."""
    if isinstance(request, Request):
        return request.replace()  # copy so we don't mutate the caller's object
    if isinstance(request, HttpRequest):
        return http_request_to_scrapy_request(request)
    return Request(url=str(request))


logger = logging.getLogger(__name__)


class DownloaderStatsMiddleware(DownloaderStats):
    def process_response(
        self, request: Request, response: Response, spider: Spider | None = None
    ) -> Request | Response:
        if isinstance(response, DummyResponse):
            return response
        kwargs = {"spider": spider} if spider is not None else {}
        return super().process_response(request, response, **kwargs)


DEFAULT_PROVIDERS = {
    HttpRequestProvider: 400,
    HttpResponseProvider: 500,
    HttpClientProvider: 600,
    PageParamsProvider: 700,
    RequestUrlProvider: 800,
    ResponseUrlProvider: 900,
    StatsProvider: 1000,
}


class InjectionMiddleware:
    """This is a Downloader Middleware that's supposed to:

    * check if request downloads could be skipped
    * inject dependencies before request callbacks are executed
    """

    def __init__(self, crawler: Crawler) -> None:
        """Initialize the middleware"""
        self.crawler = crawler
        self.registry = create_registry_instance(RulesRegistry, crawler)
        self.injector = Injector(
            crawler,
            default_providers=DEFAULT_PROVIDERS,
            registry=self.registry,
        )

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        return cls(crawler)

    def process_request(
        self, request: Request, spider: Spider | None = None
    ) -> DummyResponse | None:
        """This method checks if the request is really needed and if its
        download could be skipped by trying to infer if a :class:`scrapy.http.Response`
        is going to be used by the callback or a Page Input.

        If the :class:`scrapy.http.Response` can be ignored, a
        :class:`~.DummyResponse` instance is returned on its place. This
        :class:`~.DummyResponse` is linked to the original :class:`scrapy.Request
        <scrapy.http.Request>` instance.

        With this behavior, we're able to optimize spider executions avoiding
        unnecessary downloads. That could be the case when the callback is
        actually using another source like external APIs such as Zyte API.
        """
        if request.meta.get(_POET_PAGE_REQUEST_META_KEY):
            return None

        if self.injector.is_scrapy_response_required(request):
            return None

        logger.debug(f"Using DummyResponse instead of downloading {request}")
        assert self.crawler.stats
        self.crawler.stats.inc_value("scrapy_poet/dummy_response_count")
        return DummyResponse(url=request.url, request=request)

    def _skip_dependency_creation(self, request: Request) -> bool:
        """See:

        * https://github.com/scrapinghub/scrapy-poet/issues/48  — scrapy <  2.8
        * https://github.com/scrapinghub/scrapy-poet/issues/118 — scrapy >= 2.8
        """
        if is_min_scrapy_version("2.8.0"):
            return False

        # No need to skip if the callback doesn't default to the parse() method
        if request.callback is not None:
            return False

        # If the Request.cb_kwargs possess all of the cb dependencies, then no
        # warning message should be issued.
        assert self.crawler.spider
        signature_iter = iter(inspect.signature(self.crawler.spider.parse).parameters)
        next(signature_iter)  # skip the first arg: response
        cb_param_names = set(signature_iter)
        if cb_param_names and cb_param_names == request.cb_kwargs.keys():
            return False

        # Skip if providers are needed.
        return bool(self.injector.discover_callback_providers(request))

    async def process_response(
        self, request: Request, response: Response, spider: Spider | None = None
    ) -> Response | Request:
        """This method fills :attr:`scrapy.Request.cb_kwargs
        <scrapy.http.Request.cb_kwargs>` with instances for the required Page
        Objects found in the callback signature.

        In other words, this method instantiates all :class:`web_poet.Injectable
        <web_poet.pages.Injectable>` subclasses declared as request callback
        arguments and any other parameter with a :class:`~.PageObjectInputProvider`
        configured for its type.
        """
        if request.meta.get(_POET_PAGE_REQUEST_META_KEY):
            return response

        if self._skip_dependency_creation(request):
            warnings.warn(
                "A request has been encountered with callback=None which "
                "defaults to the parse() method. On such cases, annotated "
                "dependencies in the parse() method won't be built by "
                "scrapy-poet. However, if the request has callback=parse, "
                "the annotated dependencies will be built.\n\n"
                "See the Pitfalls doc for more info.",
                stacklevel=2,
            )
            return response

        # Find out the dependencies
        try:
            final_kwargs = await self.injector.build_callback_dependencies(
                request,
                response,
            )
        except Retry as exception:
            new_request_or_none = _get_retry_request_from_exception(
                request, exception, self.crawler
            )
            if not new_request_or_none:
                return response
            return new_request_or_none
        # Fill the callback arguments with the created instances
        for arg, value in final_kwargs.items():
            # If scrapy-poet can't provided the dependency, allow the user to
            # give it.
            if value is None and arg in request.cb_kwargs:
                continue
            request.cb_kwargs[arg] = value
            # TODO: check if all arguments are fulfilled somehow?

        return response

    async def get_page(
        self,
        request: str | Request | HttpRequest | RequestUrl | ResponseUrl,
        page_cls: type[_T],
        *,
        page_params: dict[Any, Any] | None = None,
    ) -> _T:
        """Return an instance of *page_cls* built from *request*.

        *request* can be a URL string, a :class:`scrapy.Request`, or any of
        the web-poet request types (:class:`~web_poet.HttpRequest`,
        :class:`~web_poet.RequestUrl`, :class:`~web_poet.ResponseUrl`).

        *page_params* is forwarded to the page object as a
        :class:`~web_poet.PageParams` dependency.

        Requires Scrapy 2.14+.

        Example:

        .. code-block:: python

            async def start(self):
                mw = self.crawler.get_downloader_middleware(InjectionMiddleware)
                page = await mw.get_page("https://example.com", MyPage)
                yield await page.to_item()
        """
        assert self.crawler.engine
        scrapy_request = _to_scrapy_request(request)
        if page_params is not None:
            scrapy_request.meta["page_params"] = {
                **scrapy_request.meta.get("page_params", {}),
                **page_params,
            }
        scrapy_request.meta[_POET_PAGE_REQUEST_META_KEY] = True
        response = await self.crawler.engine.download_async(scrapy_request)
        plan = self.injector.build_plan_for_type(scrapy_request, page_cls)
        instances = await self.injector.build_instances(scrapy_request, response, plan)
        if page_cls in instances:
            return instances[page_cls]
        return page_cls(**plan.final_kwargs(instances))

    async def get_item(
        self,
        request: str | Request | HttpRequest | RequestUrl | ResponseUrl,
        item_or_page_cls: type,
        *,
        page_params: dict[Any, Any] | None = None,
    ) -> Any:
        """Return an item extracted from *request*.

        *item_or_page_cls* can be either an item class or a page object class:

        - **Page class**: the page object is built and its
          :meth:`~web_poet.ItemPage.to_item` method is called.
        - **Item class**: the corresponding page class is looked up in the
          registry and used to extract the item.

        *request* and *page_params* behave the same as in :meth:`get_page`.

        Requires Scrapy 2.14+.

        Example:

        .. code-block:: python

            async def start(self):
                mw = self.crawler.get_downloader_middleware(InjectionMiddleware)
                yield await mw.get_item("https://example.com", MyItem)
        """
        if is_injectable(item_or_page_cls):
            page_cls = item_or_page_cls
        else:
            url = str(
                request.url if isinstance(request, (Request, HttpRequest)) else request
            )
            page_cls = self.registry.page_cls_for_item(url, item_or_page_cls)
            if page_cls is None:
                raise ValueError(
                    f"No page class is registered for item type {item_or_page_cls!r}."
                )
        page = await self.get_page(request, page_cls, page_params=page_params)
        item = page.to_item()
        if inspect.isawaitable(item):
            item = await item
        return item
