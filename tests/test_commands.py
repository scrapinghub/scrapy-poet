import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from web_poet.testing import Fixture

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import EchoResource, HeadersResource


def call_scrapy_command(cwd: str, *args: str) -> None:
    with tempfile.TemporaryFile() as out:
        args = (sys.executable, "-m", "scrapy.cmdline") + args
        subprocess.call(args, stdout=out, stderr=out, cwd=cwd)


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
            "ua": json.loads(self.html).get("User-Agent"),
        }
"""
    )
    type_name = "foo.po.HeadersPage"
    with MockServer(HeadersResource) as server:
        call_scrapy_command(
            str(cwd), "savefixture", type_name, server.root_url, "myspider"
        )
    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    item = json.loads(fixture.output_path.read_bytes())
    assert item == {"ua": ["scrapy/savefixture"]}


def test_savefixture_expected_exception(tmp_path) -> None:
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
    with MockServer(EchoResource) as server:
        call_scrapy_command(str(cwd), "savefixture", type_name, server.root_url)

    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    assert (
        json.loads(fixture.exception_path.read_bytes())["type_name"]
        == "web_poet.exceptions.core.UseFallback"
    )
