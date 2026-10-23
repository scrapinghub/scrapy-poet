"""An important part of scrapy-poet is the Injection Middleware. It's
responsible for injecting Page Input dependencies before the request callbacks
are executed.
"""

from __future__ import annotations

import inspect
import logging
import warnings
from functools import cached_property
from typing import TYPE_CHECKING, Self

from scrapy.downloadermiddlewares.stats import DownloaderStats
from scrapy.exceptions import NotConfigured
from scrapy.http import TextResponse
from web_poet import RulesRegistry
from web_poet.exceptions import Retry

try:
    from web_poet._frostwork import (
        _decodes_as_declared,
        _extract,
        _get_union_page,
        _response_kind,
    )
    from web_poet._selectors import _SELECTORS_DICT_ATTRIBUTE
except ImportError:  # web-poet without web_poet._frostwork
    _FROSTWORK = False
else:
    _FROSTWORK = True

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
    _navigation_values,
)
from .utils import (
    _get_retry_request_from_exception,
    create_registry_instance,
    is_min_scrapy_version,
)

if TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Request, Response

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


class NavigationMiddleware:
    """Downloader middleware that saves a parse of the response body when the
    callback gets page objects with :ref:`declarative selectors
    <web-poet:declarative-selectors>`, by reading the
    :attr:`~scrapy.http.TextResponse.base_url` and
    :attr:`~scrapy.http.TextResponse.meta_refresh` of the response in the same
    parse that extracts their fields.

    .. versionadded:: VERSION

    Its value in :setting:`DOWNLOADER_MIDDLEWARES` must be lower than that of
    :class:`~scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware`
    and higher than that of
    :class:`~scrapy.downloadermiddlewares.redirect.MetaRefreshMiddleware`.
    """

    def __init__(self, crawler: Crawler) -> None:
        # web-poet without web_poet._frostwork, or Scrapy without writable
        # TextResponse.base_url and meta_refresh.
        if not _FROSTWORK or not hasattr(TextResponse, "meta_refresh"):
            raise NotConfigured
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        return cls(crawler)

    @cached_property
    def _injector(self) -> Injector | None:
        assert self.crawler.engine
        for middleware in self.crawler.engine.downloader.middleware.middlewares:
            if isinstance(middleware, InjectionMiddleware):
                return middleware.injector
        return None

    def process_response(
        self, request: Request, response: Response, spider: Spider | None = None
    ) -> Response:
        if not isinstance(response, TextResponse) or self._injector is None:
            return response
        classes = [
            cls
            for cls, _ in self._injector.build_plan(request)
            if isinstance(cls, type)
            and hasattr(cls, _SELECTORS_DICT_ATTRIBUTE)
            and _response_kind(cls) != "browser"
        ]
        try:
            compiled = _get_union_page(classes)
        except TypeError:
            # Over the frostwork budget together. The page objects extract
            # their declarations themselves.
            return response
        if compiled is None:
            return response
        document = (response.body, response.encoding)
        if not _decodes_as_declared(document):
            return response
        values, navigation = _extract(
            compiled, document, response.url, base_url=True, meta_refresh=True
        )
        assert navigation.base_url is not None
        response.base_url = navigation.base_url
        response.meta_refresh = navigation.meta_refresh
        _navigation_values[response] = (
            response.encoding,
            values,
            navigation.base_url,
        )
        return response
