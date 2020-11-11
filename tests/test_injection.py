from scrapy.settings import Settings
from scrapy_poet import ResponseDataProvider
from scrapy_poet.injection import load_provider_classes


def test_load_provider_classes():
    provider_as_string = f"{ResponseDataProvider.__module__}.{ResponseDataProvider.__name__}"
    settings = Settings({
        "SCRAPY_POET_PROVIDER_CLASSES": [provider_as_string,
                                         ResponseDataProvider]
    })
    assert load_provider_classes(settings) == [ResponseDataProvider] * 2
