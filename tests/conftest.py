import pytest

from scrapy_poet.utils.testing import create_scrapy_settings


@pytest.fixture()
def settings():
    return create_scrapy_settings()
