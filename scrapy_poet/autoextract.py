from typing import ClassVar

import attr
from scrapy.http import Request
from scrapy.statscollectors import StatsCollector

from scrapy_poet.providers import PageObjectInputProvider

from autoextract.aio.client import request_raw
from autoextract_poet.page_inputs import (
    ProductResponseData,
    ArticleResponseData,
)


@attr.s(auto_attribs=True, slots=True)
class Query:

    url: str
    page_type: str
    full_html: bool = False

    @property
    def autoextract_query(self):
        return [
            {
                "url": self.url,
                "pageType": self.page_type,
                "fullHtml": self.full_html,
            },
        ]


class Provider(PageObjectInputProvider):

    page_type: ClassVar[str]

    def __init__(self, request: Request, stats: StatsCollector):
        self.request = request
        self.stats = stats

    async def __call__(self):
        self.stats.inc_value(f"autoextract/{self.page_type}/total")

        try:
            # FIXME: how to configure if you want full HTML or not?
            data = request_raw(self.query, max_query_error_retries=3)[0]
        except Exception:
            self.stats.inc_value(f"autoextract/{self.page_type}/error")
            raise

        self.stats.inc_value(f"autoextract/{self.page_type}/success")
        return self.provided_class(data=data)

    @property
    def query(self):
        return Query(url=self.request.url, page_type=self.page_type)


class ProductResponseDataProvider(Provider):

    page_type = "product"
    provided_class = ProductResponseData


class ArticleResponseDataProvider(Provider):

    page_type = "article"
    provided_class = ArticleResponseData
