from hashlib import md5
from pathlib import Path
from typing import Callable, Mapping

from scrapy import Request, Spider, signals
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.utils.project import get_project_settings
from scrapy_poet.injection import Injector
from scrapy_poet.overrides import PerDomainOverridesRegistry
from url_matcher.util import get_domain
from twisted.internet.defer import inlineCallbacks


class DummySpider(Spider):
    name = "dummy_spider"


def get_injector(additional_settings: Mapping) -> Injector:
    settings = get_project_settings()
    for k, v in additional_settings.items():
        settings.set(k, v)
    crawler = Crawler(DummySpider)
    crawler.settings = settings
    spider = DummySpider()
    spider.settings = settings
    crawler.spider = spider
    overrides_registry = PerDomainOverridesRegistry(
        settings.get("SCRAPY_POET_OVERRIDES")
    )
    return Injector(crawler, overrides_registry=overrides_registry)


def get_replaying_injector(fixture_path: Path) -> Injector:
    settings = dict(
        SCRAPY_POET_CACHE=str(fixture_path.absolute()),
    )
    return get_injector(settings)


class POTester:
    """
    Reply Page Objects inputs so that unit tests can be created easily
    """

    def __init__(self, url: str, po_type: Callable, tests_path: Path):
        self.url = url
        self.po_type = po_type
        self.domain = get_domain(url)
        self.tests_root_path = tests_path
        self.tests_root_path.mkdir(parents=True, exist_ok=True)
        self.fixtures_root_path = self.tests_root_path / "fixtures"
        self.fixtures_root_path.mkdir(parents=True, exist_ok=True)

        # Hash using the po_type and the url
        hash = md5(f"{po_type.__module__}.{po_type.__name__}/{url}".encode()).hexdigest()[:8]
        domain_str =self.domain.replace(".", "_").replace("-", "_")
        self.fixture_name = f"{domain_str}_{hash}.sqilte3"
        self.fixture_path = self.fixtures_root_path / self.fixture_name

    @inlineCallbacks
    def replay(self):
        """
        Replay the Page Object generation from the stored page inputs.
        Return an instance of the Page Object
        """

        def callback(page_object: self.po_type):  # type: ignore
            ...

        injector = get_replaying_injector(self.fixture_path)
        request = Request(self.url, callback)
        response = Response(self.url, request=request)

        cb_kwargs = yield injector.build_callback_dependencies(request, response)

        yield injector.crawler.signals.send_catch_log_deferred(signals.spider_closed)
        return cb_kwargs["page_object"]
