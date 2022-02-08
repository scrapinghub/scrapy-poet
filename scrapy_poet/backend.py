import logging
from contextvars import ContextVar

import scrapy
import scrapy_poet
from web_poet.page_inputs import ResponseData


logger = logging.getLogger(__name__)


def enable_backend():
    from web_poet import request_backend_var
    request_backend_var.set(scrapy_poet_backend)


# Binds the Scrapy Downloader here. The scrapy_poet.InjectionMiddleware will
# update this later when the spider starts.
scrapy_downloader_var = ContextVar("downloader")


async def scrapy_poet_backend(url):
    """To use this, frameworks must run: ``scrapy_poet.enable_backend()``."""

    if isinstance(url, str):
        request = scrapy.Request(url)

    try:
        scrapy_downloader = scrapy_downloader_var.get()
        deferred = scrapy_downloader(request)

        response = await scrapy.utils.defer.deferred_to_future(deferred)

        return ResponseData(url=response.url, html=response.text)

    except scrapy.exceptions.IgnoreRequest:
        logger.warning(f"Additional Request Ignored: {request}")
