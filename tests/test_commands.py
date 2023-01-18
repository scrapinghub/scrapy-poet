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
from web_poet import ResponseUrl
from web_poet.pages import WebPage


@attrs.define
class BTSBookPage(WebPage):

    response_url: ResponseUrl

    def to_item(self):
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
