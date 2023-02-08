import datetime
from pathlib import Path
from typing import Type

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
from web_poet.testing import Fixture

from scrapy_poet import callback_for
from scrapy_poet.downloadermiddlewares import DEFAULT_PROVIDERS, InjectionMiddleware
from scrapy_poet.injection import Injector

saved_dependencies = []
saved_items = []


class SavingInjector(Injector):
    @inlineCallbacks
    def build_instances_from_providers(
        self, request: Request, response: Response, plan: andi.Plan
    ):
        instances = yield super().build_instances_from_providers(
            request, response, plan
        )
        saved_dependencies.extend(instances.values())
        return instances


class SavingPipeline:
    def process_item(self, item, spider):
        saved_items.append(item)
        return item


class SavingInjectionMiddleware(InjectionMiddleware):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(crawler)
        self.injector = SavingInjector(
            crawler,
            default_providers=DEFAULT_PROVIDERS,
            registry=self.registry,
        )


def spider_for(injectable: Type[ItemPage]) -> Type[scrapy.Spider]:
    class InjectableSpider(scrapy.Spider):
        name = "injectable"
        url = None

        def start_requests(self):
            yield scrapy.Request(self.url, self.cb)

        cb = callback_for(injectable)

    return InjectableSpider


class SaveFixtureCommand(ScrapyCommand):
    def syntax(self):
        return "<page object class> <URL>"

    def short_desc(self):
        return "Generate a web-poet test for the provided page object and URL"

    def run(self, args, opts):
        if len(args) != 2:
            raise UsageError()
        type_name = args[0]
        url = args[1]

        cls = load_object(type_name)
        if not issubclass(cls, ItemPage):
            raise UsageError(f"Error: {type_name} is not a descendant of ItemPage")

        spider_cls = spider_for(cls)
        self.settings["ITEM_PIPELINES"][SavingPipeline] = 100
        self.settings["DOWNLOADER_MIDDLEWARES"][SavingInjectionMiddleware] = 543
        self.settings["_SCRAPY_POET_SAVEFIXTURE"] = True

        frozen_time = datetime.datetime.now(datetime.timezone.utc).replace(
            microsecond=0
        )
        with time_machine.travel(frozen_time):
            self.crawler_process.crawl(spider_cls, url=url)
            self.crawler_process.start()

        deps = saved_dependencies
        item = saved_items[0]
        meta = {
            "frozen_time": frozen_time.isoformat(timespec="seconds"),
        }
        basedir = Path(self.settings.get("SCRAPY_POET_TESTS_DIR", "fixtures"))
        fixture = Fixture.save(basedir / type_name, inputs=deps, item=item, meta=meta)
        print(f"\nThe test fixture has been written to {fixture.path}.")
