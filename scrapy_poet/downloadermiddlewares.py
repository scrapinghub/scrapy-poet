"""An important part of scrapy-poet is the Injection Middleware. It's
responsible for injecting Page Input dependencies before the request callbacks
are executed.
"""

import inspect
import logging
import warnings
from typing import Generator, Optional, Type, TypeVar, Union

from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.downloadermiddlewares.stats import DownloaderStats
from scrapy.http import Request, Response
from twisted.internet.defer import Deferred, inlineCallbacks
from web_poet import RulesRegistry
from web_poet.exceptions import Retry

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
from .utils import create_registry_instance, is_min_scrapy_version

logger = logging.getLogger(__name__)


class DownloaderStatsMiddleware(DownloaderStats):
    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Union[Request, Response]:
        if isinstance(response, DummyResponse):
            return response
        return super().process_response(request, response, spider)


DEFAULT_PROVIDERS = {
    HttpRequestProvider: 400,
    HttpResponseProvider: 500,
    HttpClientProvider: 600,
    PageParamsProvider: 700,
    RequestUrlProvider: 800,
    ResponseUrlProvider: 900,
    StatsProvider: 1000,
}

InjectionMiddlewareTV = TypeVar("InjectionMiddlewareTV", bound="InjectionMiddleware")


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
    def from_crawler(
        cls: Type[InjectionMiddlewareTV], crawler: Crawler
    ) -> InjectionMiddlewareTV:
        o = cls(crawler)
        return o

    def process_request(
        self, request: Request, spider: Spider
    ) -> Optional[DummyResponse]:
        """This method checks if the request is really needed and if its
        download could be skipped by trying to infer if a :class:`scrapy.http.Response`
        is going to be used by the callback or a Page Input.

        If the :class:`scrapy.http.Response` can be ignored, a
        :class:`~.DummyResponse` instance is returned on its place. This
        :class:`~.DummyResponse` is linked to the original :class:`scrapy.Request
        <scrapy.http.Request>` instance.

        With this behavior, we're able to optimize spider executions avoiding
        unnecessary downloads. That could be the case when the callback is
        actually using another source like external APIs such as Zyte's
        AutoExtract.
        """
        if self.injector.is_scrapy_response_required(request):
            return None

        logger.debug(f"Using DummyResponse instead of downloading {request}")
        assert self.crawler.stats
        self.crawler.stats.inc_value("scrapy_poet/dummy_response_count")
        return DummyResponse(url=request.url, request=request)

    def _skip_dependency_creation(self, request: Request, spider: Spider) -> bool:
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
        signature_iter = iter(inspect.signature(spider.parse).parameters)
        next(signature_iter)  # skip the first arg: response
        cb_param_names = set(signature_iter)
        if cb_param_names and cb_param_names == request.cb_kwargs.keys():
            return False

        # Skip if providers are needed.
        if self.injector.discover_callback_providers(request):
            return True

        return False

    @inlineCallbacks
    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Generator[Deferred, object, Union[Response, Request]]:
        """This method fills :attr:`scrapy.Request.cb_kwargs
        <scrapy.http.Request.cb_kwargs>` with instances for the required Page
        Objects found in the callback signature.

        In other words, this method instantiates all :class:`web_poet.Injectable
        <web_poet.pages.Injectable>` subclasses declared as request callback
        arguments and any other parameter with a :class:`~.PageObjectInputProvider`
        configured for its type.
        """
        if self._skip_dependency_creation(request, spider):
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
            final_kwargs = yield from self.injector.build_callback_dependencies(
                request,
                response,
            )
        except Retry as exception:
            # Needed for Twisted < 21.2.0. See the discussion thread linked below:
            # https://github.com/scrapinghub/scrapy-poet/pull/129#discussion_r1102693967
            from scrapy.downloadermiddlewares.retry import get_retry_request

            reason = str(exception) or "page_object_retry"
            new_request_or_none = get_retry_request(
                request,
                spider=spider,
                reason=reason,
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
