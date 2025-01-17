import pytest

from scrapy_poet.utils.testing import _get_test_settings


@pytest.fixture()
def settings():
    return _get_test_settings()
