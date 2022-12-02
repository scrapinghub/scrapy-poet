import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Type
from warnings import warn

from scrapy import Request
from scrapy.crawler import Crawler
from url_matcher import URLMatcher
from web_poet import ItemPage, RulesRegistry
from web_poet.rules import ApplyRule

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


class OverridesRegistry(OverridesRegistryBase, RulesRegistry):
    """
    Overrides registry that reads the overrides from the ``SCRAPY_POET_OVERRIDES``
    in the spider settings. It is a list of rules which are instances of the
    class :py:class:`web_poet.rules.ApplyRule`.

    Example of overrides configuration:

    .. code-block:: python

        from web_poet.rules import ApplyRule


        SCRAPY_POET_OVERRIDES = [
            ApplyRule(
                books.toscrape.com,
                use=ISBNBookPage,
                instead_of=BookPage,
            ),
            ApplyRule(
                "books.toscrape.com",
                use=MyBookListPage,
                instead_of=BookListPage,
            ),
        ]

    .. _web-poet: https://web-poet.readthedocs.io

    Now, if you've used web-poet_'s built-in functionality to directly create
    the :py:class:`web_poet.rules.ApplyRule` in the Page Object via the
    :py:func:`web_poet.handle_urls` annotation, you can quickly import them via
    the following code below. It finds all the rules annotated using web-poet_'s
    :py:func:`web_poet.handle_urls` as a decorator that were registered into
    ``web_poet.default_registry`` (an instance of
    :py:class:`web_poet.rules.RulesRegistry`).

    .. code-block:: python

        from web_poet import default_registry, consume_modules

        # The consume_modules() must be called first if you need to properly
        # import rules from other packages. Otherwise, it can be omitted.
        # More info about this caveat on web-poet docs.
        consume_modules("external_package_A.po", "another_ext_package.lib")
        SCRAPY_POET_OVERRIDES = default_registry.get_rules()

    Make sure to call :py:func:`web_poet.rules.consume_modules` beforehand.
    More info on this at web-poet_.
    """

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Crawler:
        return cls(crawler.settings.getlist("SCRAPY_POET_OVERRIDES", []))

    def __init__(self, rules: Optional[Iterable[ApplyRule]] = None) -> None:
        super().__init__(rules=rules)
        self.overrides_matcher: Dict[Type[ItemPage], URLMatcher] = defaultdict(
            URLMatcher
        )
        self.item_matcher: Dict[Any, URLMatcher] = defaultdict(URLMatcher)
        for rule_id, rule in enumerate(self._rules):
            self.add_rule(rule_id, rule)
        logger.debug(f"List of parsed ApplyRules:\n{self._rules}")

    def add_rule(self, rule_id: int, rule: ApplyRule) -> None:
        # A common case when a PO subclasses another one with the same URL
        # pattern. See the test_item_return_subclass() test case.
        matched = self.item_matcher[rule.to_return]
        if [
            pattern
            for pattern in matched.patterns.values()
            if pattern == rule.for_patterns
        ]:
            # TODO: It would be great to also list down the rules having the
            # same URL pattern. But this would require some refactoring.
            warn(
                f"A similar URL pattern {list(matched.patterns.values())} has been "
                f"declared earlier which uses to_return={rule.to_return}. When "
                f"matching URLs against rules, the latest declared rule is used. "
                f"Consider explicitly updating the priority of the rules containing "
                f"the said URL pattern to easily match the expectations when reading "
                f"the code."
            )

        if rule.instead_of:
            self.overrides_matcher[rule.instead_of].add_or_update(
                rule_id, rule.for_patterns
            )
        if rule.to_return:
            self.item_matcher[rule.to_return].add_or_update(rule_id, rule.for_patterns)

    # TODO: These URL matching functionalities could be moved to web-poet.

    def _run_matcher(
        self, request: Request, url_matcher
    ) -> Mapping[Callable, Callable]:
        result: Dict[Callable, Callable] = {}
        for target, matcher in url_matcher.items():
            rule_id = matcher.match(request.url)
            if rule_id is not None:
                result[target] = self._rules[rule_id].use
        return result

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        return self._run_matcher(request, self.overrides_matcher)

    def page_object_for_item(self, request: Request) -> Mapping[Callable, Callable]:
        return self._run_matcher(request, self.item_matcher)
