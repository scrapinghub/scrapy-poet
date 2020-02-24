# -*- coding: utf-8 -*-
import pytest
from scrapy.settings import Settings


@pytest.fixture()
def settings(request):
    """ Default scrapy-po settings """
    s = dict(
        # collect scraped items to .collected_items attribute
        ITEM_PIPELINES={
            'tests.utils.CollectorPipeline': 100,
        },
        DOWNLOADER_MIDDLEWARES={
            'scrapy_po.InjectionMiddleware': 543,
        },
    )
    return Settings(s)