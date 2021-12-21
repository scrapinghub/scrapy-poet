import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, Mapping, Callable, Iterable, Union, Tuple, Optional, List

from scrapy import Request
from scrapy.crawler import Crawler
from url_matcher import Patterns, URLMatcher
from url_matcher.util import get_domain
from web_poet.overrides import OverrideRule


logger = logging.getLogger(__name__)


class OverridesRegistryBase(ABC):

    @abstractmethod
    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        """
        Return a ``Mapping`` (e.g. a ``dict``) with type translation rules.
        The key is the source type that is wanted to be replaced by
        value, which is also a type.
        """
        pass


RuleAsTuple = Union[Tuple[str, Callable, Callable], List]

class OverridesRegistry(OverridesRegistryBase):
    """
    Overrides registry that reads the overrides from the ``SCRAPY_POET_OVERRIDES``
    in the spider settings. It is a list and each rule can be a tuple or an
    instance of the class ``OverrideRule``.

    If a tuple is provided:

        - the **first** element is the pattern to match the URL,
        - the **second** element is the type to be used instead of the type in
          the **third** element.

    Another way to see it for the URLs that match the pattern ``tuple[0]`` use
    ``tuple[1]`` instead of ``tuple[2]``.

    Example of overrides configuration:

    .. code-block:: python

        SCRAPY_POET_OVERRIDES = [
            ("books.toscrape.com", ISBNBookPage, BookPage),
            OverrideRule(
                for_patterns=Patterns(["books.toscrape.com"]),
                use=MyBookListPage,
                instead_of=BookListPage,
            ),
        ]

    It can be handy to compile the list of rules automatically from a module
    using the utility function ``find_page_object_overrides()`` from ``web-poet``.
    For example:

    .. code-block:: python

        from web_poet import find_page_object_overrides

        SCRAPY_POET_OVERRIDES = find_page_object_overrides("my_page_objects_module")

    It finds all the rules annotated using ``web-poet``'s ``@handle_urls``
    decorator inside the ``my_page_objects_module`` module and all of its
    submodules.

    More info on this at `web-poet <https://web-poet.readthedocs.io>`_.
    """

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        return cls(crawler.settings.getlist("SCRAPY_POET_OVERRIDES", []))

    def __init__(self, rules: Optional[Iterable[Union[RuleAsTuple, OverrideRule]]] = None):
        self.rules: List[OverrideRule] = []
        self.matcher: Dict[Callable, URLMatcher] = defaultdict(URLMatcher)
        for rule in rules or []:
            self.add_rule(rule)
        logger.debug(f"List of parsed OverrideRules:\n{self.rules}")

    def add_rule(self, rule: Union[RuleAsTuple, OverrideRule]):
        if isinstance(rule, (tuple, list)):
            if len(rule) != 3:
                raise ValueError(f"Invalid overrides rule: {rule}. Rules as tuples must have three elements: "
                                 f"the pattern, the type to override and the new type to use instead.")
            pattern, use, instead_of = rule
            rule = OverrideRule(for_patterns=Patterns([pattern]), use=use, instead_of=instead_of)
        self.rules.append(rule)
        self.matcher[rule.instead_of].add_or_update(len(self.rules) - 1, rule.for_patterns)

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        overrides = {}
        for instead_of, matcher in self.matcher.items():
            rule_id = matcher.match(request.url)
            if rule_id is not None:
                overrides[instead_of] = self.rules[rule_id].use
        return overrides
