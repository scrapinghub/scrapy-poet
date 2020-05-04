"""An important part of scrapy-poet is the Injection Middleware. It's
responsible for injecting Page Input dependencies before the request callbacks
are executed.
"""

from scrapy import Spider
from scrapy.http import Request, Response
from twisted.internet.defer import inlineCallbacks, returnValue

from scrapy_poet import utils


class InjectionMiddleware:
    """This is a Downloader Middleware that's supposed to:

    * check if request downloads could be skipped
    * inject dependencies before request callbacks are executed
    """
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
        if utils.is_response_going_to_be_used(request, spider):
            return

        spider.logger.debug(f'Skipping download of {request}')
        return utils.DummyResponse(url=request.url, request=request)

    @inlineCallbacks
    def process_response(self, request: Request, response: Response,
                         spider: Spider):
        """This method instantiates all ``Injectable`` sub-classes declared as
        request callback arguments and any other parameter with a provider for
        its type. Otherwise, this middleware doesn't populate
        ``request.cb_kwargs`` for this argument.

        .. warning::

            We should be able to inject any type into classes that inherit from
            ``web_poet.pages.Injectable``, but currently, we're only able to
            build and inject ``scrapy.Response`` instances.
        """
        # Find out the dependencies
        callback = utils.get_callback(request, spider)
        plan, provider_instances = utils.build_plan(callback, response)

        # Build all instances declared as dependencies
        instances = yield from utils.build_instances(
            plan.dependencies, provider_instances)

        # Fill the callback arguments with the created instances
        for arg, value in plan.final_kwargs(instances).items():
            # Precedence of user callback arguments
            if arg not in request.cb_kwargs:
                request.cb_kwargs[arg] = value
            # TODO: check if all arguments are fulfilled somehow?

        raise returnValue(response)
