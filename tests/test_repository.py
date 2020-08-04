import pytest

from scrapy_poet import repository
from scrapy_poet.providers import (
    ResponseData,
    ResponseDataProvider,
)
from scrapy_poet.autoextract import (
    ArticleResponseData,
    ArticleResponseDataProvider,
    ProductResponseData,
    ProductResponseDataProvider,
)


@pytest.mark.parametrize("provider, provided", [
    (ResponseDataProvider, ResponseData),
    (ArticleResponseDataProvider, ArticleResponseData),
    (ProductResponseDataProvider, ProductResponseData),
])
def test_provider_in_repository(provider, provided):
    assert repository.providers.get(provided) == provider
