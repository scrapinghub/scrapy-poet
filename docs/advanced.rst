.. _`advanced`:

==============
Advanced Usage
==============

Creating providers
==================

Providers are responsible for building dependencies needed by Injectors. A very
good example would be the ``ResponseDataProvider``, which builds and provides a
``ResponseData`` instance for Injectors that need it, like the ``ItemWebPage``.

.. code-block:: python

    @attr.s(auto_attribs=True)
    class ResponseData:
        """Represents a response containing its URL and HTML content."""
        url: str
        html: str


    @provides(ResponseData)
    class ResponseDataProvider(PageObjectInputProvider):
        """This class provides ``web_poet.page_inputs.ResponseData`` instances."""

        def __init__(self, response: Response):
            """This class receives a Scrapy ``Response`` as a dependency."""
            self.response = response

        def __call__(self):
            """This method builds a ``ResponseData`` instance using a Scrapy
            ``Response``.
            """
            return ResponseData(
                url=self.response.url,
                html=self.response.text
            )

You are able to implement your own providers in order to extend or override
current scrapy-poet behavior.

.. warning::

    Currently, scrapy-poet is only able to inject ``Response`` instances as
    provider dependencies. We should be able to overcome this limitation in the
    future.

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

.. note::

    The code above is just for example purposes. If you need to use ``Response``
    instances in your code, make use of ``ItemWebPage`` as it makes use of the
    built-ins ``ResponseData`` and ``ResponseDataProvider``.

Requests concurrency
--------------------

DummyRequests are meant to skip downloads, so it makes sense not checking for
concurrent requests, delays, or auto throttle settings since we won't be making
any download at all.

By default, if your parser or its page inputs need a regular Request, it will
be downloaded through Scrapy and all settings related to it are going to be
respected, for example:

- ``CONCURRENT_REQUESTS``
- ``CONCURRENT_REQUESTS_PER_DOMAIN``
- ``CONCURRENT_REQUESTS_PER_IP``
- ``RANDOMIZE_DOWNLOAD_DELAY``
- ``DownloaderAwarePriorityQueue``
- ``AutoThrottle``

But be aware when using third-party libraries to acquire content for a page
object. If you make an HTTP request in a provider using some third-party async
library (aiohttp, treq, etc.), ``CONCURRENT_REQUESTS`` option will be respected,
but not the other settings.

To have other settings respected, in addition to ``CONCURRENT_REQUESTS``, you'd
need to use ``crawler.engine.download`` or something like that. Alternatively,
you could implement those limits in the library itself.

In the future, it should be also possible to make use of
``DownloaderAwarePriorityQueue`` in such cases, but it will require a
refactoring on Scrapy (this is a separate task).

In the following versions of scrapy-poet, we're planning to include a new Page
Object type responsible for receiving spider-related settings. That could be
the whole Scrapy settings or just a sub-set of it. It's yet to be defined and
implemented, but that will make it easier to enforce those Scrapy settings on
providers.
