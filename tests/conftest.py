import pytest

from tests.utils import create_scrapy_settings


@pytest.fixture()
def settings(request):
    return create_scrapy_settings(request)
