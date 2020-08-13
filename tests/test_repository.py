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


def test_invalid_provider_subclass():

    class InvalidProvider:

        provided_class = ResponseData

    with pytest.raises(AssertionError):
        repository.register(InvalidProvider)


def test_instance_as_provider_argument():
    with pytest.raises(TypeError):
        repository.register("for example, string instance as provider")
