import logging

import attr
import scrapy
from scrapy.utils.defer import deferred_to_future
from web_poet.page_inputs import ResponseData
from web_poet.requests import Request, RequestBackendError


logger = logging.getLogger(__name__)


def create_scrapy_backend(backend):
    async def scrapy_backend(request: Request):
        if not isinstance(request, Request):
            raise TypeError(
                f"The request should be 'web_poet.Request' but received "
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
            response = await deferred_to_future(deferred)
            return ResponseData(
                url=response.url,
                html=response.text,
                status=response.status,
                headers=response.headers,
            )

        except scrapy.exceptions.IgnoreRequest:
            logger.warning(f"Additional Request Ignored: {request}")
    return scrapy_backend
