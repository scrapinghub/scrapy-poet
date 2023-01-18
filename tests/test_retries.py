from collections import deque
from typing import Any, List

from pytest_twisted import inlineCallbacks
from scrapy import Request, Spider
from web_poet.exceptions import Retry
from web_poet.page_inputs.http import HttpResponse
from web_poet.pages import WebPage

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource, make_crawler


class BaseSpider(Spider):
    name = "test_spider"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_poet.InjectionMiddleware": 543,
        },
        "SPIDER_MIDDLEWARES": {
            "scrapy_poet.RetryMiddleware": 275,
        },
    }


def _assert_all_unique_instances(instances: List[Any]):
    assert len({id(instance) for instance in instances}) == len(instances)


@inlineCallbacks
def test_retry_once():
    retries = deque([True, False])
    items, page_instances, page_response_instances = [], [], []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                page_instances.append(self)
                page_response_instances.append(self.response)
                if retries.popleft():
                    raise Retry
                return {"foo": "bar"}

        class TestSpider(BaseSpider):
            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]
    assert crawler.stats.get_value("downloader/request_count") == 2
    assert crawler.stats.get_value("retry/count") == 1
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") == 1
    assert crawler.stats.get_value("retry/max_reached") is None
    _assert_all_unique_instances(page_instances)
    _assert_all_unique_instances(page_response_instances)


@inlineCallbacks
def test_retry_max():
    # The default value of the RETRY_TIMES Scrapy setting is 2.
    retries = deque([True, True, False])
    items, page_instances, page_response_instances = [], [], []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                page_instances.append(self)
                page_response_instances.append(self.response)
                if retries.popleft():
                    raise Retry
                return {"foo": "bar"}

        class TestSpider(BaseSpider):
            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]
    assert crawler.stats.get_value("downloader/request_count") == 3
    assert crawler.stats.get_value("retry/count") == 2
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") == 2
    assert crawler.stats.get_value("retry/max_reached") is None
    _assert_all_unique_instances(page_instances)
    _assert_all_unique_instances(page_response_instances)


@inlineCallbacks
def test_retry_exceeded():
    items, page_instances, page_response_instances = [], [], []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                page_instances.append(self)
                page_response_instances.append(self.response)
                raise Retry

        class TestSpider(BaseSpider):
            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == []
    assert crawler.stats.get_value("downloader/request_count") == 3
    assert crawler.stats.get_value("retry/count") == 2
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") == 2
    assert crawler.stats.get_value("retry/max_reached") == 1
    _assert_all_unique_instances(page_instances)
    _assert_all_unique_instances(page_response_instances)


@inlineCallbacks
def test_retry_max_configuration():
    retries = deque([True, True, True, False])
    items, page_instances, page_response_instances = [], [], []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                page_instances.append(self)
                page_response_instances.append(self.response)
                if retries.popleft():
                    raise Retry
                return {"foo": "bar"}

        class TestSpider(BaseSpider):
            custom_settings = {
                **BaseSpider.custom_settings,
                "RETRY_TIMES": 3,
            }

            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]
    assert crawler.stats.get_value("downloader/request_count") == 4
    assert crawler.stats.get_value("retry/count") == 3
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") == 3
    assert crawler.stats.get_value("retry/max_reached") is None
    _assert_all_unique_instances(page_instances)
    _assert_all_unique_instances(page_response_instances)


@inlineCallbacks
def test_retry_cb_kwargs():
    retries = deque([True, True, False])
    items, page_instances, page_response_instances = [], [], []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                page_instances.append(self)
                page_response_instances.append(self.response)
                if retries.popleft():
                    raise Retry
                return {"foo": "bar"}

        page_from_cb_kwargs = SamplePage(
            response=HttpResponse("https://example.com", b"")
        )

        class TestSpider(BaseSpider):
            def start_requests(self):
                yield Request(
                    server.root_url,
                    callback=self.parse,
                    cb_kwargs={"page": page_from_cb_kwargs},
                )

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == [{"foo": "bar"}]
    assert crawler.stats.get_value("downloader/request_count") == 3
    assert crawler.stats.get_value("retry/count") == 2
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") == 2
    assert crawler.stats.get_value("retry/max_reached") is None
    _assert_all_unique_instances(page_instances)
    _assert_all_unique_instances(page_response_instances)
    assert page_instances[0] is not page_from_cb_kwargs
    assert page_response_instances[0] is not page_from_cb_kwargs.response


@inlineCallbacks
def test_non_retry_exception():
    items = []

    with MockServer(EchoResource) as server:

        class SamplePage(WebPage):
            def to_item(self):
                raise RuntimeError

        class TestSpider(BaseSpider):
            def start_requests(self):
                yield Request(server.root_url, callback=self.parse)

            def parse(self, response, page: SamplePage):
                items.append(page.to_item())

        crawler = make_crawler(TestSpider, {})
        yield crawler.crawl()

    assert items == []
    assert crawler.stats.get_value("downloader/request_count") == 1
    assert crawler.stats.get_value("retry/count") is None
    assert crawler.stats.get_value("retry/reason_count/page_object_retry") is None
    assert crawler.stats.get_value("retry/max_reached") is None
