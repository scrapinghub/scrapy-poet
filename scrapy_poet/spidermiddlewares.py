from typing import List, Optional

from scrapy import Spider
from scrapy.downloadermiddlewares.retry import get_retry_request
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
