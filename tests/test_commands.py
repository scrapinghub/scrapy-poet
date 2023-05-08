import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from twisted.web.resource import Resource
from web_poet.testing import Fixture

from scrapy_poet.utils.mockserver import MockServer
from scrapy_poet.utils.testing import (
    DropResource,
    EchoResource,
    ForbiddenResource,
    HeadersResource,
    ProductHtml,
)


def call_scrapy_command(cwd: str, *args: str) -> None:
    with tempfile.TemporaryFile() as out:
        args = (sys.executable, "-m", "scrapy.cmdline") + args
        status = subprocess.call(args, stdout=out, stderr=out, cwd=cwd)
        out.seek(0)
        assert status == 0, out.read().decode()


class CustomResource(Resource):
    def __init__(self):
        super().__init__()
        self.putChild(b"", ProductHtml())
        self.putChild(b"403", ForbiddenResource())
        self.putChild(b"drop", DropResource())


def test_savefixture(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name
    type_name = "foo.po.BTSBookPage"
    (cwd / project_name / "po.py").write_text(
        """
import attrs
from web_poet import HttpClient
from web_poet.exceptions import HttpRequestError, HttpResponseError
from web_poet.pages import WebPage


@attrs.define
class BTSBookPage(WebPage):

    client: HttpClient

    async def to_item(self):
        await self.client.request(self.base_url)
        try:
            await self.client.request(f"{self.base_url}/403")
        except HttpResponseError:
            pass
        try:
            await self.client.request(f"{self.base_url}/drop")
        except HttpRequestError:
            pass
        return {
            'url': self.url,
            'name': self.css("h1.name::text").get(),
        }
"""
    )

    with MockServer(CustomResource) as server:
        call_scrapy_command(
            str(cwd),
            "savefixture",
            type_name,
            f"{server.root_url}",
        )
    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    assert (fixture.input_path / "HttpResponse-body.html").exists()
    assert fixture.meta_path.exists()
    assert (fixture.input_path / "HttpClient-0-HttpResponse.body.html").exists()
    assert (fixture.input_path / "HttpClient-1-HttpResponse.body.html").exists()
    assert (fixture.input_path / "HttpClient-2-exception.json").exists()
    item = json.loads(fixture.output_path.read_bytes())
    assert item["name"] == "Chocolate"
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
        json.loads(fixture.exception_path.read_bytes())["import_path"]
        == "web_poet.exceptions.core.UseFallback"
    )


def test_savefixture_adapter(tmp_path) -> None:
    project_name = "foo"
    cwd = Path(tmp_path)
    call_scrapy_command(str(cwd), "startproject", project_name)
    cwd /= project_name
    type_name = "foo.po.BTSBookPage"
    (cwd / project_name / "po.py").write_text(
        """
from web_poet.pages import WebPage


class BTSBookPage(WebPage):
    async def to_item(self):
        return {
            'name': self.css("h1.name::text").get(),
        }
"""
    )
    (cwd / project_name / "settings.py").write_text(
        """
from collections import deque

from itemadapter.adapter import DictAdapter, ItemAdapter


class LowercaseDictAdapter(DictAdapter):
    def __getitem__(self, field_name):
        item = super().__getitem__(field_name)
        if isinstance(item, str):
            return item.lower()
        return item


class CustomItemAdapter(ItemAdapter):
    ADAPTER_CLASSES = deque([LowercaseDictAdapter])


SCRAPY_POET_TESTS_ADAPTER = CustomItemAdapter
"""
    )

    with MockServer(ProductHtml) as server:
        call_scrapy_command(
            str(cwd),
            "savefixture",
            type_name,
            f"{server.root_url}",
        )
    fixtures_dir = cwd / "fixtures"
    fixture_dir = fixtures_dir / type_name / "test-1"
    fixture = Fixture(fixture_dir)
    assert fixture.is_valid()
    item = json.loads(fixture.output_path.read_bytes())
    assert item == {"name": "chocolate"}
