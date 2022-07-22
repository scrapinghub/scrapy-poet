from .api import DummyResponse, callback_for
from .middleware import InjectionMiddleware
from .page_input_providers import (
    CacheDataProviderMixin,
    HttpResponseProvider,
    PageObjectInputProvider,
)

try:
    from .spidermiddlewares import RetrySpiderMiddleware
except ImportError:
    pass
