from abc import ABC, abstractmethod
from collections import Callable
from typing import Dict, Mapping

from scrapy import Request
from scrapy.crawler import Crawler
from scrapy_poet.utils import get_domain


class OverridesRegistryBase(ABC):

    @abstractmethod
    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        pass


class PerDomainOverridesRegistry(Dict[str, Dict[Callable, Callable]], OverridesRegistryBase):

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        return cls(crawler.settings.getdict("SCRAPY_POET_OVERRIDES", {}))

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        return self.get(get_domain(request.url), {})


