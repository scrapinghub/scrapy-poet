from autoextract_poet.inputs import (
    ResponseData,
    ProductResponseData,
    ProductListResponseData,
)
from autoextract_poet.utils import Query, QueryLevelError


def test_autoextract_responses():
    data = {"foo": "bar"}
    assert ResponseData(data=data).data == data
    assert ProductResponseData(data=data).data == data
    assert ProductListResponseData(data=data).data == data


def test_autoextract_query():
    query = Query("example.com", "myPageType")
    assert query.url == "example.com"
    assert query.page_type == "myPageType"
    assert query.full_html is True
    assert query.autoextract_query == [
        {
            'url': 'example.com',
            'pageType': 'myPageType',
            'fullHtml': True,
        },
    ]

    query = Query("example.com", "myPageType", False)
    assert query.full_html is False
    assert query.autoextract_query == [
        {
            'url': 'example.com',
            'pageType': 'myPageType',
            'fullHtml': False,
        },
    ]


def test_query_level_error_exception():
    query = Query("example.com", "myPageType")
    exc = QueryLevelError(query, "error")
    assert exc.query == query
    assert exc.msg == "error"
