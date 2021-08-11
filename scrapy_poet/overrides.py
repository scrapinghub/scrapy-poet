from abc import ABC, abstractmethod
from typing import Dict, Mapping, Callable, Optional, List

from marisa_trie import Trie

from scrapy import Request
from scrapy.crawler import Crawler
from scrapy_poet.utils import get_domain, url_hierarchical_str


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


class OverridesRecord:

    def __init__(self, hierarchical_url: str, overrides: Mapping[Callable, Callable]):
        self.hierarchical_url = hierarchical_url
        self.overrides = overrides


class HierarchicalOverridesRegistry(OverridesRegistryBase):
    """
    Overrides registry that reads the overrides
    from the option ``SCRAPY_POET_OVERRIDES`` in the spider settings

    Example of overrides configuration:

    .. code-block:: python

        SCRAPY_POET_OVERRIDES = {
            "example.com": {
                BookPage: ExampleBookPage
                BookListPage: ExampleListBookPage
            }
        }

    The former example configures ``ExampleBookPage``
    and ``ExampleListBookPage`` to be used instead
    of ``BookPage`` and ``BookListPage`` respectively
    for any request to the domain ``example.com``.

    Each set of rules can be configured to override a particular
    domain, subdomain or even a specific path. The following
    table shows some examples of keys and what are they effect.

    .. list-table:: Overrides keys examples
       :widths: auto
       :width: 80%
       :header-rows: 1

       * - Key
         - The overrides apply to
       * - ``"subdomain.example.com"``
         - any request belonging to ``subdomain.example.com`` or any of its
           subdomains
       * - ``"example.com/path_to_content"``
         - any request to the netlocs ``example.com`` or ``www.example.com`` whose
           URL path is a children of ``/path_to_content``
       * - ``""``
         - any request. Useful to set default overrides

    **The most specific rule is applied** when several rules could be
    applied to the same URL. Imagine, for example, the case where you have rules
    for ``""``, ``"toscrape.com"``, ``"books.toscrape.com"`` and ``"books.toscrape.com/catalogue"``:

    * The rules for ``""`` would be applied for the URL ``http://example.com``
    * The rules for ``"toscrape.com"`` would be applied for the URL ``http://toscrape.com/index.html``
    * The rules for ``"books.toscrape.com"`` would be applied for the URL ``http://books.toscrape.com``
    * The rules for ``"books.toscrape.com/catalogue"`` would be applied for the URL ``http://books.toscrape.com/catalogue/category``

    This is useful as it allows to configure some general overrides for a site
    and also some more specific overrides for some subsections of the site.
    """

    def __init__(self, all_overrides: Optional[Mapping[str, Mapping[Callable, Callable]]] = None) -> None:
        super().__init__()
        self.overrides: List[OverridesRecord] = []
        self.trie = Trie()
        for domain_or_more, overrides in (all_overrides or {}).items():
            self.register(domain_or_more, overrides)

    def register(self, domain_or_more: str, overrides: Mapping[Callable, Callable]):
        url = f"http://{domain_or_more}"
        hurl = url_hierarchical_str(url)
        record = OverridesRecord(hurl, overrides)
        # Update case
        if hurl in self.trie:
            self.overrides[self.trie[hurl]] = record
            return

        # Insert case. We have to rebuild the trie and the reindex the
        # overrides list based on the new trie.
        # Note that this is O(N), but register is expected to be executed only
        # at initialization and we expect N to be low enough.
        new_overrides = self.overrides + [record]
        self.trie = Trie([override.hierarchical_url for override in new_overrides])
        self.overrides = [None] * len(new_overrides)  # type: ignore
        for override in new_overrides:
            self.overrides[self.trie[override.hierarchical_url]] = override

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        return cls(crawler.settings.getdict("SCRAPY_POET_OVERRIDES", {}))

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        hurl = url_hierarchical_str(request.url)
        max_prefix = max(self.trie.prefixes(hurl), default=None)
        if max_prefix is not None:
            return self.overrides[self.trie[max_prefix]].overrides
        else:
            return {}
