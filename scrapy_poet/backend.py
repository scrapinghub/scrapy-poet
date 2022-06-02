import logging

import attr
import scrapy
from scrapy.utils.defer import maybe_deferred_to_future
from web_poet import HttpRequest
from web_poet.exceptions import (
    HttpError,
    HttpRequestError,
    RequestBackendError,
)

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
            request = scrapy.Request(**attr.asdict(request), dont_filter=True)
        except TypeError:
            raise RequestBackendError(
                f"The given Request isn't compatible with `scrapy.Request`. "
                f"Ensure that it doesn't contain extra fields: {request}"
            )

        if request.method == "HEAD":
            request.meta["dont_redirect"] = True

        deferred = backend(request)
        deferred_or_future = maybe_deferred_to_future(deferred)
        try:
            response = await deferred_or_future
        except scrapy.exceptions.IgnoreRequest:
            raise HttpError(f"Additional request ignored: {request}")
        except Exception:
            raise HttpRequestError(f"Additional request failed: {request}")

        return scrapy_response_to_http_response(response)

    return scrapy_backend
