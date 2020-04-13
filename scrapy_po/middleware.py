# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from scrapy import Request

from scrapy_po import utils


class InjectionMiddleware:
    """
    This downloader middleware instantiates all Injectable subclasses declared
    as request callback arguments and any other parameter with a provider
    for its type. Otherwise this middleware doesn't populate request.cb_kwargs
    for this argument.

    XXX: should it really be a downloader middleware?
    """
    def process_request(self, request: Request, spider):
        """Check if the request is needed and if the download can be skipped.

        Here we try to infer if the request's response is going to be used
        by its designated parser or an injected Page Object.

        If we evaluate that the request could be ignored, we return a
        utils.DummyResponse object linked to the original Request instance.

        With this behavior we're able to optimize spider executions avoid
        having to download URLs twice or when they're not needed, for example,
        when a Page Object relies only on a third-party API like AutoExtract.
        """
        if utils.is_response_going_to_be_used(request, spider):
            return

        spider.logger.debug(f'Skipping download of {request}')
        return utils.DummyResponse(url=request.url, request=request)

    @inlineCallbacks
    def process_response(self, request: Request, response, spider):
        # find out the dependencies
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
