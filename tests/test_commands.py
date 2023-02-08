import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from web_poet.testing import Fixture


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
    assert (
        fixture.input_path
        / "HttpClient-4a4c68d01cec0684e4eb2d155534005ac2db9a33-body.html"
    ).exists()
    frozen_time_str = json.loads(fixture.meta_path.read_bytes())["frozen_time"]
    frozen_time = datetime.datetime.fromisoformat(frozen_time_str)
    assert frozen_time.microsecond == 0
