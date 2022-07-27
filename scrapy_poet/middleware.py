from warnings import warn

from .downloadermiddlewares import InjectionMiddleware  # # noqa: F401

warn(
    "The scrapy_poet.middleware module is deprecated, use "
    "scrapy_poet.downloadermiddlewares instead."
)
