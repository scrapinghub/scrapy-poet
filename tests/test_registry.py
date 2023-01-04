import pytest
from scrapy import Spider
from scrapy.utils.test import get_crawler
from web_poet import ApplyRule, ItemPage


def test_OverridesRegistry() -> None:
    from scrapy_poet.overrides import OverridesRegistry

    msg = (
        "scrapy_poet.registry.OverridesRegistry is deprecated, "
        "instantiate scrapy_poet.registry.OverridesAndItemRegistry instead."
    )
    with pytest.warns(DeprecationWarning, match=msg):
        OverridesRegistry()


def test_deprecation_setting_SCRAPY_POET_OVERRIDES(settings) -> None:
    from scrapy_poet.registry import OverridesAndItemRegistry

    class FakePageObjectA(ItemPage):
        pass

    rule_a = ApplyRule("https://example.com", use=FakePageObjectA)

    settings["SCRAPY_POET_OVERRIDES"] = [rule_a]
    crawler = get_crawler(Spider, settings)

    msg = (
        "The SCRAPY_POET_OVERRIDES setting is deprecated. "
        "Use SCRAPY_POET_RULES instead."
    )
    with pytest.warns(DeprecationWarning, match=msg):
        registry = OverridesAndItemRegistry.from_crawler(crawler)

    assert registry.get_rules() == [rule_a]

    # If both settings are present, the newer SCRAPY_POET_RULES setting is used.

    class FakePageObjectB(ItemPage):
        pass

    rule_b = ApplyRule("https://example.com", use=FakePageObjectB)
    settings["SCRAPY_POET_RULES"] = [rule_b]
    crawler = get_crawler(Spider, settings)

    with pytest.warns(DeprecationWarning, match=msg):
        registry = OverridesAndItemRegistry.from_crawler(crawler)

    assert registry.get_rules() == [rule_b]
