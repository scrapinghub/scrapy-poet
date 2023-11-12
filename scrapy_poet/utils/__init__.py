import os
from functools import lru_cache
from typing import Type
from warnings import warn

from packaging.version import Version
from scrapy import __version__ as SCRAPY_VERSION
from scrapy.crawler import Crawler
from scrapy.http import HtmlResponse, Request, Response
from scrapy.utils.project import inside_project, project_data_dir
from scrapy.utils.response import open_in_browser as scrapy_open_in_browser
from web_poet import (
    HttpRequest,
    HttpResponse,
    HttpResponseHeaders,
    consume_modules,
    default_registry,
)

try:
    from scrapy.http.request import NO_CALLBACK  # available on Scrapy >= 2.8
except ImportError:
    # NO_CALLBACK = lambda: None  # noqa: E731
    NO_CALLBACK = None


def get_scrapy_data_path(createdir: bool = True, default_dir: str = ".scrapy") -> str:
    """Return a path to a folder where Scrapy is storing data.

    Usually that's a .scrapy folder inside the project.
    """
    # This code is extracted from scrapy.utils.project.data_path function,
    # which does too many things.
    path = project_data_dir() if inside_project() else default_dir
    if createdir:
        os.makedirs(path, exist_ok=True)
    return path


def http_request_to_scrapy_request(request: HttpRequest, **kwargs) -> Request:
    return Request(
        url=str(request.url),
        method=request.method,
        headers=request.headers,
        body=request.body,
        callback=NO_CALLBACK,
        **kwargs,
    )


def scrapy_response_to_http_response(response: Response) -> HttpResponse:
    """Convenience method to convert a ``scrapy.http.Response`` into a
    ``web_poet.HttpResponse``.
    """
    kwargs = {}
    encoding = getattr(response, "_encoding", None)
    if encoding:
        kwargs["encoding"] = encoding
    return HttpResponse(
        url=response.url,
        body=response.body,
        status=response.status,
        headers=HttpResponseHeaders.from_bytes_dict(response.headers),
        **kwargs,
    )


def open_in_browser(response):
    scrapy_open_in_browser(http_response_to_scrapy_response(response))


def http_response_to_scrapy_response(response: HttpResponse) -> HtmlResponse:
    """Convenience method to convert a ``web_poet.HttpResponse`` into a
    ``scrapy.http.HtmlResponse``.
    """
    kwargs = {}
    encoding = getattr(response, "_encoding", None) or "utf-8"
    kwargs["encoding"] = encoding

    return HtmlResponse(
        url=response.url._url,
        body=response.text,
        status=response.status,
        headers=response.headers,
        **kwargs,
    )


def create_registry_instance(cls: Type, crawler: Crawler):
    for module in crawler.settings.getlist("SCRAPY_POET_DISCOVER", []):
        consume_modules(module)
    if "SCRAPY_POET_OVERRIDES" in crawler.settings:
        msg = (
            "The SCRAPY_POET_OVERRIDES setting is deprecated. "
            "Use SCRAPY_POET_RULES instead."
        )
        warn(msg, DeprecationWarning, stacklevel=2)
    rules = crawler.settings.getlist(
        "SCRAPY_POET_RULES",
        crawler.settings.getlist("SCRAPY_POET_OVERRIDES", default_registry.get_rules()),
    )
    return cls(rules=rules)


@lru_cache()
def is_min_scrapy_version(version: str) -> bool:
    return Version(SCRAPY_VERSION) >= Version(version)
