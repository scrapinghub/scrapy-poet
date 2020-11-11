"""An important part of scrapy-poet is the Injection Middleware. It's
responsible for injecting Page Input dependencies before the request callbacks
are executed.
"""
from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.settings import Settings
from scrapy.statscollectors import StatsCollector
from twisted.internet.defer import inlineCallbacks, returnValue

from scrapy_poet import utils
from scrapy_poet.utils import _SCRAPY_PROVIDED_CLASSES, load_provider_classes


class Injector:

    def __init__(self, crawler: Crawler):
        self.crawler = crawler
        self.spider = crawler.spider
        self.load_providers()

    def load_providers(self):
        self.providers = [
            cls(self.crawler)
            for cls in load_provider_classes(self.crawler.settings)
        ]
        # Caching whether each provider requires the scrapy response
        self.is_provider_requiring_scrapy_response = {
            id(provider): utils.is_provider_requiring_scrapy_response(provider)
            for provider in self.providers
        }

    def available_dependencies_for_providers(self,
                                             request: Request,
                                             response: Response):
        deps = {
            Crawler: self.crawler,
            Spider: self.spider,
            Settings: self.spider.settings,
            StatsCollector: self.crawler.stats,
            Request: request,
            Response: response,
        }
        assert deps.keys() == _SCRAPY_PROVIDED_CLASSES
        return deps

    def is_scrapy_response_required(self, request: Request):
        """
        Check whether the request's response is going to be used.
        """
        callback = utils.get_callback(request, self.spider)
        if utils.is_callback_requiring_scrapy_response(callback):
            return True

        for provider in utils.discover_callback_providers(callback, self.providers):
            if self.is_provider_requiring_scrapy_response[id(provider)]:
                return True

        return False

    @inlineCallbacks
    def build_callback_dependencies(self, request: Request, response: Response):
        """
        Scan the configured callback for this response looking for the
        dependencies and build the instances for them. Return a kwargs
        dictionary with the built instances.
        """
        callback = utils.get_callback(request, self.spider)
        plan = utils.build_plan(callback, self.providers)
        provider_instances = yield from utils.build_instances(
            plan,
            self.providers,
            self.available_dependencies_for_providers(request, response)
        )
        callback_kwargs = plan.final_kwargs(provider_instances)
        raise returnValue(callback_kwargs)


class InjectionMiddleware:
    """This is a Downloader Middleware that's supposed to:

    * check if request downloads could be skipped
    * inject dependencies before request callbacks are executed
    """
    def __init__(self, crawler):
        self.crawler = crawler
        self.injector = Injector(crawler)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_request(self, request: Request, spider: Spider):
        """This method checks if the request is really needed and if its
        download could be skipped by trying to infer if a ``Response``
        is going to be used by the callback or a Page Input.

        If the ``Response`` can be ignored, a ``utils.DummyResponse`` object is
        returned on its place. This ``DummyResponse`` is linked to the original
        ``Request`` instance.

        With this behavior, we're able to optimize spider executions avoiding
        unnecessary downloads. That could be the case when the callback is
        actually using another source like external APIs such as Scrapinghub's
        Auto Extract.
        """
        if self.injector.is_scrapy_response_required(request):
            return

        spider.logger.debug(f'Skipping download of {request}')
        return utils.DummyResponse(url=request.url, request=request)

    @inlineCallbacks
    def process_response(self, request: Request, response: Response,
                         spider: Spider):
        """This method instantiates all ``Injectable`` subclasses declared as
        request callback arguments and any other parameter with a provider for
        its type. Otherwise, this middleware doesn't populate
        ``request.cb_kwargs`` for this argument.

        If there's a collision between an already set ``cb_kwargs``
        and an injectable attribute,
        the user-defined ``cb_kwargs`` takes precedence.

        Currently, we are able to inject instances of the following
        classes as *provider* dependencies:

        - :class:`~scrapy.Spider`
        - :class:`~scrapy.http.Request`
        - :class:`~scrapy.http.Response`
        - :class:`~scrapy.crawler.Crawler`
        - :class:`~scrapy.settings.Settings`
        - :class:`~scrapy.statscollectors.StatsCollector`
        """
        # Find out the dependencies
        final_kwargs = yield from self.injector.build_callback_dependencies(
            request,
            response
        )
        # Fill the callback arguments with the created instances
        for arg, value in final_kwargs.items():
            # Precedence of user callback arguments
            if arg not in request.cb_kwargs:
                request.cb_kwargs[arg] = value
            # TODO: check if all arguments are fulfilled somehow?

        raise returnValue(response)
