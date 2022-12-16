import datetime
import sys
from pathlib import Path
from typing import Type

import andi
import scrapy
from freezegun import freeze_time
from scrapy import Request
from scrapy.commands import ScrapyCommand
from scrapy.crawler import Crawler
from scrapy.http import Response
from scrapy.utils.misc import load_object
from twisted.internet.defer import inlineCallbacks
from web_poet import ItemPage
from web_poet.testing import save_fixture

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
            overrides_registry=self.overrides_registry,
        )


def spider_for(injectable: Type[ItemPage]) -> Type[scrapy.Spider]:
    class InjectableSpider(scrapy.Spider):
        name = "injectable"

        url = None
        custom_settings = {
            "SCRAPY_POET_PROVIDERS": DEFAULT_PROVIDERS,
        }

        def start_requests(self):
            yield scrapy.Request(self.url, self.cb)

        cb = callback_for(injectable)

    return InjectableSpider


def additional_settings() -> dict:
    return {
        "ITEM_PIPELINES": {
            SavingPipeline: 100,
        },
        "DOWNLOADER_MIDDLEWARES": {
            SavingInjectionMiddleware: 543,
        },
    }


class CreatePOTestCommand(ScrapyCommand):
    def run(self, args, opts):
        assert len(args) == 3
        basedir = Path(args[0])
        po_name = args[1]
        url = args[2]

        po_type = load_object(po_name)
        if not issubclass(po_type, ItemPage):
            print(f"Error: {po_name} is not a descendant of ItemPage")
            sys.exit(1)

        spider_cls = spider_for(po_type)
        self.settings.setdict(additional_settings())

        frozen_time = datetime.datetime.utcnow().isoformat()
        with freeze_time(frozen_time):
            crawler = Crawler(spider_cls, self.settings)
            self.crawler_process.crawl(crawler, url=url)
            self.crawler_process.start()

        deps = saved_dependencies
        item = saved_items[0]
        meta = {
            "frozen_time": frozen_time,
        }
        fixture_dir = save_fixture(basedir / po_name, deps, item, meta=meta)
        print(f"\nThe test fixture has been written to {fixture_dir}.")
