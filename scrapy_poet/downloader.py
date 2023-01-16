import logging

from scrapy.exceptions import IgnoreRequest
from scrapy.utils.defer import maybe_deferred_to_future
from web_poet import HttpRequest
from web_poet.exceptions import HttpError, HttpRequestError

from scrapy_poet.utils import (
    http_request_to_scrapy_request,
    scrapy_response_to_http_response,
)

logger = logging.getLogger(__name__)


def create_scrapy_downloader(download_func):
    async def scrapy_downloader(request: HttpRequest):
        if not isinstance(request, HttpRequest):
            raise TypeError(
                f"The request should be 'web_poet.HttpRequest' but received "
                f"one of type: {type(request)!r}."
            )

        scrapy_request = http_request_to_scrapy_request(request)

        if scrapy_request.method == "HEAD":
            scrapy_request.meta["dont_redirect"] = True

        deferred = download_func(scrapy_request)
        deferred_or_future = maybe_deferred_to_future(deferred)
        try:
            response = await deferred_or_future
        except IgnoreRequest as e:
            # A Scrapy downloader middleware has caused the request to be
            # ignored.
            message = f"Additional request ignored: {scrapy_request}"
            raise HttpError(message) from e
        except Exception as e:
            # This could be caused either by network errors (Twisted
            # exceptions, OpenSSL, exceptions, etc.) or by unhandled exceptions
            # in Scrapy downloader middlewares. We assume the former (raise
            # HttpRequestError instead of HttpError), it being the most likely,
            # and the latter only happening due to badly written code.
            message = f"Additional request failed: {scrapy_request}"
            raise HttpRequestError(message) from e

        return scrapy_response_to_http_response(response)

    return scrapy_downloader
