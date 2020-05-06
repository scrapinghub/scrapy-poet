.. _`advanced`:

==============
Advanced Usage
==============

Creating providers
==================

Blah

Ignoring requests
=================

Sometimes requests could be skipped, for example, when you're fetching data
using a third-party API such as Auto Extract or querying a database.

In cases like that, it makes no sense to send the request to Scrapy's downloader
as it will only waste network resources. But there's an alternative to avoid
making such requests, you could use ``DummyRequests`` type to annotate
your response arguments.

That could be done in the spider's parser method:

.. code-block:: python

    def parser(self, response: DummyRequest, page: MyPageObject):
        pass

Spiders that annotate its first argument as ``DummyResponse`` are signaling that
they're not going to make use of it, so it should be safe to skip it from our
downloader middleware. This type annotation is already applied when you use the
``callback_for`` helper.

If neither spider callback or any of the input providers are going to make use
of a ``Response``, our Injection Middleware skips download returning a
``DummyResponse`` instead. For example:

.. code-block:: python

    def get_cached_content(key: str):
        # get cached html response from db or other source
        pass


    @attr.s(auto_attribs=True)
    class CachedData:

        key: str
        value: str


    @provides(CachedData)
    class CachedDataProvider(PageObjectInputProvider):

        def __init__(self, response: DummyResponse):
            self.response = response

        def __call__(self):
            return CachedData(
                key=self.response.url,
                value=get_cached_content(self.response.url)
            )


    class MyPageObject(ItemPage):

        content: CachedData

        def to_item(self):
            return {
                'url': self.content.key,
                'content': self.content.value,
            }


    class MySpider(scrapy.Spider):

        name = 'my_spider'

        def parse(self, response: DummyResponse, page: MyPageObject):
            # request will be IGNORED because neither spider callback
            # not MyPageObject seem like to be making use of its response
            yield page.to_item()

Although, if the spider callback is not going to use the ``Response``, but the
Page Object makes use of it, the request is not going to be ignored and will be
processed, for example:

.. code-block:: python

    def parse_content(html: str):
        # parse content from html
        pass


    @attr.s(auto_attribs=True)
    class MyResponseData:

        url: str
        html: str


    @provides(MyResponseData)
    class MyResponseDataProvider(PageObjectInputProvider):

        def __init__(self, response: Response):
            self.response = response

        def __call__(self):
            return MyResponseData(
                url=self.response.url,
                html=self.response.content,
            )


    class MyPageObject(ItemPage):

        response: MyResponseData

        def to_item(self):
            return {
                'url': self.response.url,
                'content': parse_content(self.response.html),
            }


    class MySpider(scrapy.Spider):

        name = 'my_spider'

        def parse(self, response: DummyResponse, page: MyPageObject):
            # request will be PROCESSED because spider callback is not
            # making use of its response, but MyPageObject seems like to be
            yield page.to_item()

.. warning::

    The code above is just for example purposes. If you need to use ``Response``
    instances in your code, make use of ``ItemWebPage`` as it makes use of the
    built-ins ``ResponseData`` and ``ResponseDataProvider``.

.. _`advanced-bar`:

Bar
===

asd