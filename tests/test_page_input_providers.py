import pytest

from scrapy_poet import PageObjectInputProvider
from scrapy_poet.injection_errors import MalformedProvidedClassesError


class TestProvider:

    def test_is_provided_on_malformed_provided_classes(self):
        class Provider(PageObjectInputProvider):
            provided_classes = [str]

        with pytest.raises(MalformedProvidedClassesError) as excinfo:
            Provider(None).is_provided(str)

        assert "Unexpected type" in str(excinfo.value)
        assert "Provider" in str(excinfo.value)
        assert "Expected either 'set' or 'callable'" in str(excinfo.value)

    def test_is_provided_on_function(self):
        class Provider(PageObjectInputProvider):
            @staticmethod
            def provided_classes(cls):
                return issubclass(cls, str)

        class SubStr(str):
            pass

        provider = Provider(None)
        assert provider.is_provided(str)
        assert provider.is_provided(SubStr)
        assert not provider.is_provided(float)

    def test_is_provided_on_set(self):
        class Provider(PageObjectInputProvider):
            provided_classes = {str, int}

        provider = Provider(None)
        assert provider.is_provided(str)
        assert provider.is_provided(int)
        assert not provider.is_provided(float)
