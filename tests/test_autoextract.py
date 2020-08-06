from scrapy_poet.autoextract import Query


def test_autoextract_query():
    query = Query("example.com", "myPageType")
    assert query.url == "example.com"
    assert query.pageType == "myPageType"
    assert query.fullHtml is False
    assert query.autoextract_query == [
        {
            'url': 'example.com',
            'pageType': 'myPageType',
            'fullHtml': False,
            'articleBodyRaw': False,
            'meta': None,
        },
    ]

    query = Query("example.com", "myPageType", fullHtml=True)
    assert query.fullHtml is True
    assert query.autoextract_query == [
        {
            'url': 'example.com',
            'pageType': 'myPageType',
            'fullHtml': True,
            'articleBodyRaw': False,
            'meta': None,
        },
    ]

    query = Query("example.com", "myPageType", extra=dict(foo="bar"))
    assert query.url == "example.com"
    assert query.pageType == "myPageType"
    assert query.fullHtml is False
    assert query.autoextract_query == [
        {
            'url': 'example.com',
            'pageType': 'myPageType',
            'fullHtml': False,
            'articleBodyRaw': False,
            'meta': None,
            'foo': 'bar',
        },
    ]
