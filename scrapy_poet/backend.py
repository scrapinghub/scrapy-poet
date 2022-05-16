import logging

import attr
import scrapy
from scrapy.utils.defer import deferred_to_future
from web_poet import HttpRequest
from web_poet.exceptions import RequestBackendError

from scrapy_poet.utils import scrapy_response_to_http_response


logger = logging.getLogger(__name__)


def create_scrapy_backend(backend):
    async def scrapy_backend(request: HttpRequest):
        if not isinstance(request, HttpRequest):
            raise TypeError(
                f"The request should be 'web_poet.HttpRequest' but received "
                f"one of type: '{type(request)}'."
            )

        try:
            request = scrapy.Request(**attr.asdict(request))
        except TypeError:
            raise RequestBackendError(
                f"The given Request isn't compatible with `scrapy.Request`. "
                f"Ensure that it doesn't contain extra fields: {request}"
            )

        try:
            deferred = backend(request)
            response: scrapy.http.Response = await deferred_to_future(deferred)
            return scrapy_response_to_http_response(response)

        except scrapy.exceptions.IgnoreRequest:
            logger.warning(f"Additional Request Ignored: {request}")
    return scrapy_backend
