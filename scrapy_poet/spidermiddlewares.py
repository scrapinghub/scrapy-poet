from __future__ import annotations

from typing import TYPE_CHECKING

from web_poet.exceptions import Retry

if TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.http import Request, Response


class RetryMiddleware:
    """Captures :exc:`web_poet.exceptions.Retry` exceptions from spider
    callbacks, and retries the source request."""

    def process_spider_exception(
        self,
        response: Response,
        exception: BaseException,
        spider: Spider,
    ) -> list[Request] | None:
        # Needed for Twisted < 21.2.0. See the discussion thread linked below:
        # https://github.com/scrapinghub/scrapy-poet/pull/129#discussion_r1102693967
        from scrapy.downloadermiddlewares.retry import (  # noqa: PLC0415
            get_retry_request,
        )

        if not isinstance(exception, Retry):
            return None
        assert response.request
        new_request_or_none = get_retry_request(
            response.request,
            spider=spider,
            reason=str(exception) or "page_object_retry",
        )
        if not new_request_or_none:
            return []
        return [new_request_or_none]
