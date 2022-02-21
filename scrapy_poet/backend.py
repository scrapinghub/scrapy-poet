import logging
from contextvars import ContextVar
from typing import Union

import attr
import scrapy
import scrapy_poet
from scrapy.utils.defer import deferred_to_future
from web_poet.page_inputs import ResponseData
from web_poet.requests import Request, RequestBackendError


logger = logging.getLogger(__name__)


def enable_backend():
    from web_poet.requests import request_backend_var
    request_backend_var.set(scrapy_poet_backend)


# Binds the Scrapy Downloader here. The scrapy_poet.InjectionMiddleware will
# update this later when the spider starts.
scrapy_downloader_var: ContextVar = ContextVar("downloader")


async def scrapy_poet_backend(request: Union[Request, scrapy.Request]):
    """To use this, frameworks must run: ``scrapy_poet.enable_backend()``.

    The request could either be ``web_poet.Request`` or even a
    ``scrapy.Request`` to give developers more fine grain control.
    """

    if not isinstance(request, scrapy.Request):
        try:
            request = scrapy.Request(**attr.asdict(request))
        except TypeError:
            raise RequestBackendError(
                f"The given Request isn't compatible with `scrapy.Request`. "
                f"Ensure that it doesn't contain extra fields: {request}"
            )

    try:
        scrapy_downloader = scrapy_downloader_var.get()
        deferred = scrapy_downloader(request)

        response = await deferred_to_future(deferred)

        return ResponseData(
            url=response.url,
            html=response.text,
            status=response.status,
            headers=response.headers,
        )

    except scrapy.exceptions.IgnoreRequest:
        logger.warning(f"Additional Request Ignored: {request}")
