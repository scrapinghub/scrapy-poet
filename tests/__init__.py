import os

from scrapy import Spider
from scrapy.crawler import Crawler
from scrapy.utils.test import get_crawler as _get_crawler

# Note that tox.ini should only set the REACTOR env variable when running
# pytest with "--reactor=asyncio".
if os.environ.get("REACTOR", "") == "asyncio":
    from scrapy.utils.reactor import install_reactor

    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")


def get_download_handler(crawler, schema):
    return crawler.engine.downloader.handlers._get_handler(schema)


def setup_crawler_engine(crawler: Crawler):
    """Run the crawl steps until engine setup, so that crawler.engine is not
    None.

    https://github.com/scrapy/scrapy/blob/8fbebfa943c3352f5ba49f46531a6ccdd0b52b60/scrapy/crawler.py#L116-L122
    """

    crawler.crawling = True
    crawler.spider = crawler._create_spider()
    crawler.engine = crawler._create_engine()

    handler = get_download_handler(crawler, "https")
    if hasattr(handler, "engine_started"):
        handler.engine_started()


class DummySpider(Spider):
    name = "dummy"


def get_crawler(settings=None, spider_cls=DummySpider, setup_engine=True):
    settings = settings or {}
    crawler = _get_crawler(settings_dict=settings, spidercls=spider_cls)
    if setup_engine:
        setup_crawler_engine(crawler)
    return crawler
