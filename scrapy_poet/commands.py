import datetime
import logging
from pathlib import Path
from typing import Dict, Optional, Type

import andi
import scrapy
import time_machine
from scrapy import Request
from scrapy.commands import ScrapyCommand
from scrapy.crawler import Crawler
from scrapy.exceptions import UsageError
from scrapy.http import Response
from scrapy.utils.misc import load_object
from twisted.internet.defer import inlineCallbacks
from web_poet import ItemPage
from web_poet.exceptions import PageObjectAction
from web_poet.testing import Fixture
from web_poet.utils import ensure_awaitable

from scrapy_poet import DummyResponse
from scrapy_poet.downloadermiddlewares import DEFAULT_PROVIDERS, InjectionMiddleware
from scrapy_poet.injection import Injector

logger = logging.getLogger(__name__)


saved_dependencies = []
saved_items = []
saved_exceptions = []
frozen_time = None


class SavingInjector(Injector):
    @inlineCallbacks
    def build_instances_from_providers(
        self,
        request: Request,
        response: Response,
        plan: andi.Plan,
        prev_instances: Optional[Dict] = None,
    ):
        instances = yield super().build_instances_from_providers(
            request, response, plan, prev_instances
        )
        if request.meta.get("savefixture", False):
            saved_dependencies.extend(instances.values())
        return instances


class SavingInjectionMiddleware(InjectionMiddleware):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(crawler)
        self.injector = SavingInjector(
            crawler,
            default_providers=DEFAULT_PROVIDERS,
            registry=self.registry,
        )


def spider_for(
    injectable: Type[ItemPage],
    url: str,
    base_spider: Optional[Type[scrapy.Spider]] = None,
) -> Type[scrapy.Spider]:
    if base_spider is None:
        base_spider = scrapy.Spider

    class InjectableSpider(base_spider):  # type: ignore[valid-type, misc]
        name = "injectable"

        def __init__(self, name=None, **kwargs):
            super().__init__(name, **kwargs)
            meta = {"savefixture": True}
            self.start_requests = lambda: [scrapy.Request(url, self.cb, meta=meta)]

        async def cb(self, response: DummyResponse, page: injectable):  # type: ignore[valid-type]
            global frozen_time
            frozen_time = datetime.datetime.now(datetime.timezone.utc).replace(
                microsecond=0
            )
            with time_machine.travel(frozen_time):
                try:
                    item = await ensure_awaitable(page.to_item())  # type: ignore[attr-defined]
                except PageObjectAction as ex:
                    # let other exception types fail the test generation
                    saved_exceptions.append(ex)
                else:
                    saved_items.append(item)
                    yield item

    return InjectableSpider


class SaveFixtureCommand(ScrapyCommand):
    def syntax(self):
        return "<page object class> <URL> [<spider name>]"

    def short_desc(self):
        return "Generate a web-poet test for the provided page object and URL"

    def run(self, args, opts):
        if len(args) < 2:
            raise UsageError()
        type_name = args[0]
        url = args[1]

        cls = load_object(type_name)
        if not issubclass(cls, ItemPage):
            raise UsageError(f"Error: {type_name} is not a descendant of ItemPage")

        self.settings["DOWNLOADER_MIDDLEWARES"][
            "scrapy_poet.InjectionMiddleware"
        ] = None
        self.settings["DOWNLOADER_MIDDLEWARES"][
            "scrapy_poet.downloadermiddlewares.InjectionMiddleware"
        ] = None
        self.settings["DOWNLOADER_MIDDLEWARES"][InjectionMiddleware] = None
        self.settings["DOWNLOADER_MIDDLEWARES"][SavingInjectionMiddleware] = 543
        self.settings["_SCRAPY_POET_SAVEFIXTURE"] = True

        base_spider_cls = None
        if len(args) > 2:
            spider_name = args[2]
            spider_loader = self.crawler_process.spider_loader
            try:
                base_spider_cls = spider_loader.load(spider_name)
            except KeyError:
                logger.error(f"Unable to find spider: {spider_name}")
                return
        spider_cls = spider_for(cls, url, base_spider_cls)
        self.crawler_process.crawl(spider_cls)
        self.crawler_process.start()

        if not saved_items and not saved_exceptions:
            logger.error(
                "No items were scraped and no handled exceptions were caught, check the spider output."
            )
            self.exitcode = 1
            return
        deps = saved_dependencies
        meta = {
            "frozen_time": frozen_time.isoformat(timespec="seconds"),
        }
        adapter = self.settings.get("SCRAPY_POET_TESTS_ADAPTER")
        if adapter:
            meta["adapter"] = load_object(adapter)
        basedir = Path(self.settings.get("SCRAPY_POET_TESTS_DIR", "fixtures"))
        if saved_items:
            item = saved_items[0]
            fixture = Fixture.save(
                basedir / type_name, inputs=deps, item=item, meta=meta
            )
        else:
            exception = saved_exceptions[0]
            fixture = Fixture.save(
                basedir / type_name, inputs=deps, exception=exception, meta=meta
            )
        logger.info(f"\nThe test fixture has been written to {fixture.path}.")
