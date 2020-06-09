from autoextract_poet.inputs import (
    AutoExtractResponseData,
    AutoExtractProductResponseData,
    AutoExtractProductListResponseData,
)
from autoextract_poet.exceptions import QueryLevelError


def test_autoextract_responses():
    data = {"foo": "bar"}
    assert AutoExtractResponseData(data=data).data == data
    assert AutoExtractProductResponseData(data=data).data == data
    assert AutoExtractProductListResponseData(data=data).data == data


def test_query_level_error_exception():
    exc = QueryLevelError("my_url", "myPageType", ["query", "args"], "error")
    assert exc.url == "my_url"
    assert exc.page_type == "myPageType"
    assert exc.query == ["query", "args"]
    assert exc.msg == "error"
