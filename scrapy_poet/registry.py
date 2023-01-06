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
from web_poet.utils import _create_deprecated_class

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


class OverridesAndItemRegistry(OverridesRegistryBase, RulesRegistry):
    """This registry implements the functionalities for returning the override
    for a given request as well as returning the page object capable of returning
    an item class for a given URL.

    Read the :ref:`rules-from-web-poet` tutorial for more information.

    It reads the rules from the ``SCRAPY_POET_RULES`` setting which is a list of
    :py:class:`web_poet.rules.ApplyRule` instances:

    .. code-block:: python

        from web_poet import default_registry

        SCRAPY_POET_RULES = default_registry.get_rules()

    .. _web-poet: https://web-poet.readthedocs.io

    Calling ``default_registry.get_rules()`` finds all the rules annotated using
    web-poet_'s :py:func:`web_poet.handle_urls` as a decorator that were registered
    into ``web_poet.default_registry`` (an instance of
    :py:class:`web_poet.rules.RulesRegistry`).

    .. warning::

        The :py:func:`web_poet.rules.consume_modules` must be called first
        if you need to properly import rules from other packages. For example:

        .. code-block:: python

            from web_poet import default_registry, consume_modules

            consume_modules("external_package_A.po", "another_ext_package.lib")
            SCRAPY_POET_RULES = default_registry.get_rules()

    """

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Crawler:
        if "SCRAPY_POET_OVERRIDES" in crawler.settings:
            msg = (
                "The SCRAPY_POET_OVERRIDES setting is deprecated. "
                "Use SCRAPY_POET_RULES instead."
            )
            warn(msg, DeprecationWarning, stacklevel=2)
        rules = crawler.settings.getlist(
            "SCRAPY_POET_RULES",
            crawler.settings.getlist("SCRAPY_POET_OVERRIDES", []),
        )
        return cls(rules=rules)

    def __init__(self, rules: Optional[Iterable[ApplyRule]] = None) -> None:
        super().__init__(rules=rules)
        self.overrides_matcher: Dict[Type[ItemPage], URLMatcher] = defaultdict(
            URLMatcher
        )
        self.item_matcher: Dict[Optional[Type], URLMatcher] = defaultdict(URLMatcher)
        for rule_id, rule in enumerate(self._rules):
            self.add_rule(rule_id, rule)
        logger.debug(f"List of parsed ApplyRules:\n{self._rules}")

    def add_rule(self, rule_id: int, rule: ApplyRule) -> None:
        """Registers an :class:`web_poet.rules.ApplyRule` instance against the
        given rule ID.
        """
        # A common case when a page object subclasses another one with the same
        # URL pattern. See the ``test_item_return_subclass()`` test case in
        # ``tests/test_web_poet_rules.py``.
        matched = self.item_matcher[rule.to_return]
        pattern_dupes = [
            pattern
            for pattern in matched.patterns.values()
            if pattern == rule.for_patterns
        ]
        if pattern_dupes:
            rules = [
                r
                for p in pattern_dupes
                for r in self.search(for_patterns=p, to_return=rule.to_return)
            ]
            warn(
                f"Similar URL patterns {pattern_dupes} were declared earlier "
                f"that use to_return={rule.to_return}. The first, highest-priority "
                f"rule added to SCRAPY_POET_REGISTRY will be used when matching "
                f"against URLs. Consider updating the priority of these rules: "
                f"{rules}."
            )

        if rule.instead_of:
            self.overrides_matcher[rule.instead_of].add_or_update(
                rule_id, rule.for_patterns
            )
        if rule.to_return:
            self.item_matcher[rule.to_return].add_or_update(rule_id, rule.for_patterns)

    # TODO: These URL matching functionalities could be moved to web-poet.
    # ``overrides_for`` in web-poet could be ``str`` or ``_Url`` subclass.

    def _rules_for_url(
        self, url: str, url_matcher: Dict[Any, URLMatcher]
    ) -> Mapping[Callable, Callable]:
        result: Dict[Callable, Callable] = {}
        for target, matcher in url_matcher.items():
            rule_id = matcher.match(url)
            if rule_id is not None:
                result[target] = self._rules[rule_id].use
        return result

    def overrides_for(self, request: Request) -> Mapping[Callable, Callable]:
        return self._rules_for_url(request.url, self.overrides_matcher)

    def page_object_for_item(
        self, url: str, po_cls: Type[Any]
    ) -> Optional[Callable[..., Any]]:
        """Returns the page object class for a given URL and item class."""
        return self._rules_for_url(url, self.item_matcher).get(po_cls)


OverridesRegistry = _create_deprecated_class(
    "OverridesRegistry", OverridesAndItemRegistry, warn_once=False
)
