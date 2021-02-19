from abc import ABC, abstractmethod
from typing import Dict, Mapping, Callable

from scrapy import Request
from scrapy.crawler import Crawler
from scrapy_poet.utils import get_domain


class OverridesRegistryBase(ABC):

    @abstractmethod
    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        """
        Return a ``Mapping`` (e.g. a ``dict``) with type translation rules.
        The key is the source type that is wanted to be replaced by
        value, which is also a type.
        """
        pass


class PerDomainOverridesRegistry(Dict[str, Dict[Callable, Callable]], OverridesRegistryBase):
    """
    Simple dictionary based registry that reads the overrides
    from the option ``SCRAPY_POET_OVERRIDES`` in the spider settings

    Example of overrides configuration:

    .. code-block:: python

        SCRAPY_POET_OVERRIDES = {
            "example.com": {
                BookPage: ISBNBookPage
            }
        }
    """

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        return cls(crawler.settings.getdict("SCRAPY_POET_OVERRIDES", {}))

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        return self.get(get_domain(request.url), {})


