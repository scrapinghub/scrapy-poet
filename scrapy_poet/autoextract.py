from typing import ClassVar, Optional

import attr
from scrapy.http import Request
from scrapy.settings import Settings
from scrapy.statscollectors import StatsCollector

from scrapy_poet.providers import PageObjectInputProvider

from autoextract.aio.client import request_raw
from autoextract_poet.page_inputs import (
    ProductResponseData,
    ArticleResponseData,
)


@attr.s(auto_attribs=True, slots=True)
class Query:
    """Represent an AutoExtract Query.

    There are some basic parameters such as `url` and `pageType` that could be
    defined during initialization. If you need to specify additional params,
    you can do it using the `extra` argument, an optional dictionary that
    will be expanded to update the final query object.
    """

    url: str
    pageType: str
    articleBodyRaw: bool = False
    fullHtml: bool = False
    meta: Optional[str] = None
    extra: Optional[dict] = None

    @property
    def autoextract_query(self):
        query = attr.asdict(self)
        query.update(**self.extra or {})
        del query["extra"]
        return [query]


class Provider(PageObjectInputProvider):

    page_type: ClassVar[str]

    def __init__(
            self,
            request: Request,
            settings: Settings,
            stats: StatsCollector,
    ):
        self.request = request
        self.stats = stats
        self.settings = settings

    async def __call__(self):
        self.stats.inc_value(f"autoextract/{self.page_type}/total")

        try:
            # FIXME: how to configure if you want full HTML or not?
            data = await request_raw(
                self.query.autoextract_query,
                api_key=self.settings.get('SCRAPINGHUB_AUTOEXTRACT_KEY'),
                max_query_error_retries=3
            )[0]
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
