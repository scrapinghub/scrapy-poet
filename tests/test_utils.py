from unittest import mock
from pathlib import PosixPath

import pytest
from scrapy import Request
from web_poet import HttpRequest

from scrapy_poet.utils import (
    get_scrapy_data_path,
    http_request_to_scrapy_request,
)


@mock.patch("scrapy_poet.utils.os.makedirs")
@mock.patch("scrapy_poet.utils.inside_project")
def test_get_scrapy_data_path(mock_inside_project, mock_makedirs, tmp_path):
    mock_inside_project.return_value = False

    path = tmp_path / "test_dir"
    result = get_scrapy_data_path(createdir=True, default_dir=path)

    assert isinstance(result, PosixPath)
    assert str(result)  # should be non-empty

    mock_inside_project.assert_called_once()

    mock_makedirs.assert_called_once()
    mock_makedirs.assert_called_with(path, exist_ok=True)


@pytest.mark.parametrize(
    "http_request,kwargs,scrapy_request",
    (
        (
            HttpRequest("https://example.com"),
            {},
            Request("https://example.com"),
        ),
        (
            HttpRequest("https://example.com"),
            {"dont_filter": True},
            Request("https://example.com", dont_filter=True),
        ),
        (
            HttpRequest("https://example.com", method="POST"),
            {},
            Request("https://example.com", method="POST"),
        ),
        (
            HttpRequest("https://example.com", headers={"a": "b"}),
            {},
            Request("https://example.com", headers={"a": "b"}),
        ),
        (
            HttpRequest("https://example.com", headers={"a": "b"}),
            {},
            Request("https://example.com", headers=(("a", "b"),)),
        ),
        (
            HttpRequest("https://example.com", headers=(("a", "b"),)),
            {},
            Request("https://example.com", headers=(("a", "b"),)),
        ),
        (
            HttpRequest(
                "https://example.com",
                headers=(("a", "b"), ("a", "c")),
            ),
            {},
            Request(
                "https://example.com",
                headers=(("a", "b"), ("a", "c")),
            ),
        ),
        (
            HttpRequest("https://example.com", body=b"a"),
            {},
            Request("https://example.com", body=b"a"),
        ),
    ),
)
def test_http_request_to_scrapy_request(http_request, kwargs, scrapy_request):
    result = http_request_to_scrapy_request(http_request, **kwargs)
    assert result.url == scrapy_request.url
    assert result.method == scrapy_request.method
    assert result.headers == scrapy_request.headers
    assert result.body == scrapy_request.body
    assert result.meta == scrapy_request.meta
    assert result.cb_kwargs == scrapy_request.cb_kwargs
    assert result.cookies == scrapy_request.cookies
    assert result.encoding == scrapy_request.encoding
    assert result.priority == scrapy_request.priority
    assert result.dont_filter == scrapy_request.dont_filter
    assert result.callback == scrapy_request.callback
    assert result.errback == scrapy_request.errback
    assert result.flags == scrapy_request.flags
