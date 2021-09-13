import re
from typing import Mapping

import pytest

from scrapy import Request, Spider
from scrapy.utils.test import get_crawler
from scrapy_poet.overrides import RegexOverridesRegistry, \
    PerDomainOverridesRegistry, domain_or_more_regex


class _str(str, Mapping):  # type: ignore
    """Trick to use strings as overrides dicts for testing"""
    ...


def _r(url: str):
    return Request(url)


@pytest.fixture
def reg():
    return RegexOverridesRegistry()


class TestRegexOverridesRegistry:

    def test_replace(self, reg):
        reg.register("toscrape.com", _str("ORIGINAL"))
        assert reg.overrides_for(_r("http://toscrape.com:442/path")) == "ORIGINAL"
        reg.register("toscrape.com", _str("REPLACED"))
        assert reg.overrides_for(_r("http://www.toscrape.com/path")) == "REPLACED"
        assert len(reg.rules) == 1

    def test_init_and_global(self):
        overrides = {
            "": _str("GLOBAL"),
            "toscrape.com": _str("TOSCRAPE")
        }
        reg = RegexOverridesRegistry(overrides)
        assert reg.overrides_for(_r("http://example.com/blabla")) == "GLOBAL"
        assert reg.overrides_for(_r("http://toscrape.com/blabla")) == "TOSCRAPE"

    def test_register(self, reg):
        assert reg.overrides_for(_r("http://books.toscrape.com/")) == {}

        reg.register("books.toscrape.com", _str("BOOKS_TO_SCRAPE"))
        assert reg.overrides_for(_r("http://books.toscrape.com/")) == "BOOKS_TO_SCRAPE"
        assert reg.overrides_for(_r("http://books.toscrape.com/path")) == "BOOKS_TO_SCRAPE"
        assert reg.overrides_for(_r("http://toscrape.com/")) == {}

        reg.register("toscrape.com", _str("TO_SCRAPE"))
        assert reg.overrides_for(_r("http://books.toscrape.com/")) == "BOOKS_TO_SCRAPE"
        assert reg.overrides_for(_r("http://books.toscrape.com/path")) == "BOOKS_TO_SCRAPE"
        assert reg.overrides_for(_r("http://toscrape.com/")) == "TO_SCRAPE"
        assert reg.overrides_for(_r("http://www.toscrape.com/")) == "TO_SCRAPE"
        assert reg.overrides_for(_r("http://toscrape.com/path")) == "TO_SCRAPE"
        assert reg.overrides_for(_r("http://zz.com")) == {}

        reg.register("books.toscrape.com/category/books/classics_6/", _str("CLASSICS"))
        assert reg.overrides_for(_r("http://books.toscrape.com/path?arg=1")) == "BOOKS_TO_SCRAPE"
        assert reg.overrides_for(_r("http://toscrape.com")) == "TO_SCRAPE"
        assert reg.overrides_for(_r("http://aa.com")) == {}
        assert reg.overrides_for(
            _r("https://books.toscrape.com/category/books/classics_6")) == "CLASSICS"
        assert reg.overrides_for(
            _r("http://books.toscrape.com/category/books/classics_6/path")) == "CLASSICS"
        assert reg.overrides_for(
            _r("http://books.toscrape.com/category/books/")) == "BOOKS_TO_SCRAPE"

    def test_from_crawler(self):
        crawler = get_crawler(Spider)
        reg = RegexOverridesRegistry.from_crawler(crawler)
        assert len(reg.rules) == 0

        settings = {
            "SCRAPY_POET_OVERRIDES": {
                "toscrape.com": _str("TOSCRAPE")
            }
        }
        crawler = get_crawler(Spider, settings)
        reg = RegexOverridesRegistry.from_crawler(crawler)
        assert len(reg.rules) == 1
        assert reg.overrides_for(_r("http://toscrape.com/path")) == "TOSCRAPE"

    def test_domain_subdomain_case(self, reg):
        reg.register("toscrape.com", _str("DOMAIN"))
        reg.register("books.toscrape.com", _str("SUBDOMAIN"))
        assert reg.overrides_for(_r("http://toscrape.com/blabla")) == "DOMAIN"
        assert reg.overrides_for(_r("http://cars.toscrape.com/")) == "DOMAIN"
        assert reg.overrides_for(_r("http://books2.toscrape.com:123/blabla")) == "DOMAIN"
        assert reg.overrides_for(_r("https://mybooks.toscrape.com/blabla")) == "DOMAIN"
        assert reg.overrides_for(_r("http://books.toscrape.com/blabla")) == "SUBDOMAIN"
        assert reg.overrides_for(_r("http://www.books.toscrape.com")) == "SUBDOMAIN"
        assert reg.overrides_for(_r("http://uk.books.toscrape.com/blabla")) == "SUBDOMAIN"

    def test_common_prefix_domains(self, reg):
        reg.register("toscrape.com", _str("TOSCRAPE"))
        reg.register("toscrape2.com", _str("TOSCRAPE2"))
        assert reg.overrides_for(_r("http://toscrape.com/blabla")) == "TOSCRAPE"
        assert reg.overrides_for(_r("http://toscrape2.com")) == "TOSCRAPE2"


class TestPerDomainOverridesRegistry:

    def test(self):
        settings = {
            "SCRAPY_POET_OVERRIDES": {
                "toscrape.com": _str("TOSCRAPE")
            }
        }
        crawler = get_crawler(Spider, settings)
        reg = PerDomainOverridesRegistry.from_crawler(crawler)
        assert reg.overrides_for(_r("http://toscrape.com/path")) == "TOSCRAPE"
        assert reg.overrides_for(_r("http://books.toscrape.com/path")) == "TOSCRAPE"
        assert reg.overrides_for(_r("http://toscrape2.com/path")) == {}


@pytest.mark.parametrize("domain_or_more",
                         [
                             "", "example.com:343", "example.com:343/",
                             "WWW.example.com:343/",
                             "www.EXAMPLE.com:343/?id=23",
                             "www.example.com:343/page?id=23",
                             "www.example.com:343/page?id=23;params#fragment",
                             "127.0.0.1:80/page?id=23;params#fragment",
                             "127.0.0.1:443/page?id=23;params#fragment",
                             "127.0.0.1:333/page?id=23;params#fragment"
                         ])
def test_domain_or_more_regex(domain_or_more):
    url = f"http://{domain_or_more}"
    regex = domain_or_more_regex(domain_or_more)

    assert re.match(regex, url)
    assert re.match(regex, f"https://{domain_or_more}")
    assert re.match(regex, url + "a")
    assert re.match(regex, url + "/")
    assert re.match(regex, url + "/some_text")
    assert re.match(regex, url + "some_other_text")

    if url[-1] == '/' and domain_or_more:
        assert re.match(regex, url[:-1])
        assert not re.match(regex, url[:-2])
        url = url[:-1]  # The polluted test requires the url without a last slash
    else:
        assert not re.match(regex, url[:-1])
    for i in range(len(url)):
        # Modify a single character
        polluted = url[:i] + chr(ord(url[i]) - 1) + url[i+1:]
        assert not re.match(regex, polluted)