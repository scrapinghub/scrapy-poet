import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from web_poet.testing import Fixture

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource


def call_scrapy_command(cwd: str, *args: str) -> None:
    with tempfile.TemporaryFile() as out:
        args = (sys.executable, "-m", "scrapy.cmdline") + args
        subprocess.call(args, stdout=out, stderr=out, cwd=cwd)
        out.seek(0)
        pass


def test_savefixture(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name
    type_name = "foo.po.BTSBookPage"
    (cwd / project_name / "po.py").write_text(
        """
import attrs
from web_poet import HttpClient, ResponseUrl
from web_poet.pages import WebPage


@attrs.define
class BTSBookPage(WebPage):

    response_url: ResponseUrl
    client: HttpClient

    async def to_item(self):
        await self.client.request("http://toscrape.com")
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }
"""
    )
    url = "http://books.toscrape.com/catalogue/the-wedding-pact-the-omalleys-2_767/index.html"
    call_scrapy_command(str(cwd), "savefixture", type_name, url)
    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    assert (fixture.input_path / "HttpResponse-body.html").exists()
    assert fixture.meta_path.exists()
    assert (fixture.input_path / "HttpClient-0-HttpResponse.body.html").exists()
    frozen_time_str = json.loads(fixture.meta_path.read_bytes())["frozen_time"]
    frozen_time = datetime.datetime.fromisoformat(frozen_time_str)
    assert frozen_time.microsecond == 0


def test_savefixture_spider(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name

    (cwd / project_name / "spiders" / "spider.py").write_text(
        """
from scrapy import Spider


class MySpider(Spider):
    name = "myspider"
    custom_settings = {
        "USER_AGENT": "scrapy/savefixture",
    }
"""
    )

    (cwd / project_name / "po.py").write_text(
        """
import json
from web_poet.pages import WebPage


class HeadersPage(WebPage):
    async def to_item(self):
        return {
            "ua": json.loads(self.html)["headers"].get("User-Agent"),
        }
"""
    )
    url = "http://httpbin.org/headers"
    type_name = "foo.po.HeadersPage"
    call_scrapy_command(str(cwd), "savefixture", type_name, url, "myspider")
    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    item = json.loads(fixture.output_path.read_bytes())
    assert item == {"ua": "scrapy/savefixture"}


def test_savefixture_exceptions_retry(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name
    type_name = "foo.po.SamplePage"
    (cwd / project_name / "po.py").write_text(
        """
from collections import deque

from web_poet.exceptions import Retry
from web_poet.pages import WebPage


retries = deque([True, False])


class SamplePage(WebPage):
    def to_item(self):
        if retries.popleft():
            raise Retry
        return {"foo": "bar"}
"""
    )
    (cwd / project_name / "spiders/retry.py").write_text(
        """
import scrapy_poet
from scrapy import Request, Spider

from foo.po import SamplePage


class TestSpider(Spider):
    name = "test_spider"

    custom_settings = {
        "SPIDER_MIDDLEWARES": {
            "scrapy_poet.RetryMiddleware": 275,
        },
    }

    def parse(self, response, page: SamplePage):
        pass
"""
    )
    with MockServer(EchoResource) as server:
        call_scrapy_command(
            str(cwd), "savefixture", type_name, server.root_url, "test_spider"
        )

    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    assert (fixture.input_path / "HttpResponse-body.html").exists()
    assert json.loads(fixture.output_path.read_bytes()) == {"foo": "bar"}


@pytest.mark.xfail(reason="The generated test doesn't handle UseFallback.")
def test_savefixture_exceptions_usefallback(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name
    type_name = "foo.po.SamplePage"
    (cwd / project_name / "po.py").write_text(
        """
from web_poet.exceptions import UseFallback
from web_poet.pages import WebPage


class SamplePage(WebPage):
    def to_item(self):
        raise UseFallback
"""
    )
    (cwd / project_name / "spiders/retry.py").write_text(
        """
import scrapy_poet
from scrapy import Request, Spider
from web_poet.exceptions import UseFallback

from foo.po import SamplePage


class TestSpider(Spider):
    name = "test_spider"

    def parse(self, response, page: SamplePage):
        try:
            return page.to_item()
        except UseFallback:
            return {"foo": "bar"}
"""
    )
    with MockServer(EchoResource) as server:
        call_scrapy_command(
            str(cwd), "savefixture", type_name, server.root_url, "test_spider"
        )

    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    assert json.loads(fixture.output_path.read_bytes()) == {"foo": "bar"}
