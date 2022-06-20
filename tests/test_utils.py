from pathlib import PosixPath
from unittest import mock

import pytest
from scrapy.http import Request, Response, TextResponse
from web_poet import HttpRequest, HttpResponse

from scrapy_poet.utils import (
    get_scrapy_data_path,
    http_request_to_scrapy_request,
    scrapy_response_to_http_response,
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


@pytest.mark.parametrize(
    "scrapy_response,http_response",
    (
        (
            Response("https://example.com"),
            HttpResponse("https://example.com", body=b"", status=200),
        ),
        (
            Response("https://example.com", body=b"a"),
            HttpResponse("https://example.com", body=b"a", status=200),
        ),
        (
            Response("https://example.com", status=429),
            HttpResponse("https://example.com", body=b"", status=429),
        ),
        (
            Response("https://example.com", headers={"a": "b"}),
            HttpResponse(
                "https://example.com",
                body=b"",
                status=200,
                headers={"a": "b"},
            ),
        ),
        (
            Response("https://example.com", headers={"a": "b"}),
            HttpResponse(
                "https://example.com",
                body=b"",
                status=200,
                headers=(("a", "b"),),
            ),
        ),
        (
            Response("https://example.com", headers=(("a", "b"),)),
            HttpResponse(
                "https://example.com",
                body=b"",
                status=200,
                headers=(("a", "b"),),
            ),
        ),
        pytest.param(
            Response("https://example.com", headers=(("a", "b"), ("a", "c"))),
            HttpResponse(
                "https://example.com",
                body=b"",
                status=200,
                headers=(("a", "b"), ("a", "c")),
            ),
            marks=pytest.mark.xfail(
                reason="https://github.com/scrapy/scrapy/issues/5515",
            ),
        ),
        (
            TextResponse("https://example.com", body="a", encoding="ascii"),
            HttpResponse(
                "https://example.com", body=b"a", status=200, encoding="ascii"
            ),
        ),
        (
            TextResponse("https://example.com", body="a", encoding="utf-8"),
            HttpResponse(
                "https://example.com", body=b"a", status=200, encoding="utf-8"
            ),
        ),
    ),
)
def test_scrapy_response_to_http_response(scrapy_response, http_response):
    result = scrapy_response_to_http_response(scrapy_response)
    assert str(result.url) == str(http_response.url)
    assert result.body == http_response.body
    assert result.status == http_response.status
    assert result.headers == http_response.headers
    assert result._encoding == http_response._encoding
