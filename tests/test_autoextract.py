from scrapy_poet.autoextract import Query


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
