from autoextract_poet.inputs import (
    ResponseData,
    ProductResponseData,
    ProductListResponseData,
)
from autoextract_poet.exceptions import QueryLevelError


def test_autoextract_responses():
    data = {"foo": "bar"}
    assert ResponseData(data=data).data == data
    assert ProductResponseData(data=data).data == data
    assert ProductListResponseData(data=data).data == data


def test_query_level_error_exception():
    exc = QueryLevelError(["my_url", "myPageType"], "error")
    assert exc.query == ["my_url", "myPageType"]
    assert exc.msg == "error"
