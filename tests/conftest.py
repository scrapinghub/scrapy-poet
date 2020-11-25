import pytest
from scrapy.settings import Settings

from scrapy_poet.page_input_providers import ResponseDataProvider


@pytest.fixture()
def settings(request):
    """ Default scrapy-poet settings """
    s = dict(
        # collect scraped items to .collected_items attribute
        ITEM_PIPELINES={
            'tests.utils.CollectorPipeline': 100,
        },
        DOWNLOADER_MIDDLEWARES={
            'scrapy_poet.InjectionMiddleware': 543,
        }
    )
    return Settings(s)
