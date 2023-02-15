from typing import List, Optional

from scrapy import Spider
from scrapy.http import Request, Response
from web_poet.exceptions import Retry


class RetryMiddleware:
    """Captures :exc:`web_poet.exceptions.Retry` exceptions from spider
    callbacks, and retries the source request."""

    def process_spider_exception(
        self,
        response: Response,
        exception: BaseException,
        spider: Spider,
    ) -> Optional[List[Request]]:
        # Needed for Twisted < 21.2.0. See the discussion thread linked below:
        # https://github.com/scrapinghub/scrapy-poet/pull/129#discussion_r1102693967
        from scrapy.downloadermiddlewares.retry import get_retry_request

        if not isinstance(exception, Retry):
            return None
        new_request_or_none = get_retry_request(
            response.request,
            spider=spider,
            reason="page_object_retry",
        )
        if not new_request_or_none:
            return []
        return [new_request_or_none]
