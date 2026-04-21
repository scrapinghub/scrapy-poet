from __future__ import annotations

from typing import TYPE_CHECKING

from web_poet.exceptions import Retry

from .utils import _get_retry_request_from_exception

if TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.http import Request, Response


class RetryMiddleware:
    """Captures :exc:`web_poet.exceptions.Retry` exceptions from spider
    callbacks, and retries the source request."""

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.crawler = crawler
        return obj

    def process_spider_exception(
        self,
        response: Response,
        exception: BaseException,
        spider: Spider | None = None,
    ) -> list[Request] | None:
        if not isinstance(exception, Retry):
            return None
        assert response.request
        new_request_or_none = _get_retry_request_from_exception(
            response.request, exception, self.crawler
        )
        if not new_request_or_none:
            return []
        return [new_request_or_none]
