.. _providers:

=========
Providers
=========

.. note::

    This document assumes a good familiarity with ``web-poet`` concepts;
    make sure you've read ``web-poet`` docs_.

    This page is mostly aimed at developers who want to extend ``scrapy-poet``,
    **not** to developers who are writing extraction and crawling code using
    ``scrapy-poet``.


.. _docs: https://web-poet.readthedocs.io/en/stable/

Creating providers
==================

Providers are responsible for building dependencies needed by Injectable
objects. A good example would be the ``HttpResponseProvider``,
which builds and provides a ``web_poet.HttpResponse`` instance for Injectables
that need it, like the ``web_poet.ItemWebPage``.

.. code-block:: python

    import attr
    from typing import Set, Callable

    import web_poet
    from scrapy_poet.page_input_providers import PageObjectInputProvider
    from scrapy import Response


    class HttpResponseProvider(PageObjectInputProvider):
        """This class provides ``web_poet.HttpResponse`` instances."""
        provided_classes = {web_poet.HttpResponse}

        def __call__(self, to_provide: Set[Callable], response: Response):
            """Build a ``web_poet.HttpResponse`` instance using a Scrapy ``Response``"""
            return [
                web_poet.HttpResponse(
                    url=response.url,
                    body=response.body,
                    status=response.status,
                    headers=web_poet.HttpResponseHeaders.from_bytes_dict(response.headers),
                )
            ]

You can implement your own providers in order to extend or override current
``scrapy-poet`` behavior. All providers should inherit from this base class:
:class:`~.PageObjectInputProvider`.

Please, check the docs provided in the following API reference for more details:
:class:`scrapy_poet.page_input_providers.PageObjectInputProvider`.


Cache Suppport in Providers
===========================

``scrapy-poet`` also supports caching of the provided dependencies from the
providers. For example, :class:`~.HttpResponseProvider` supports this right off
the bat. It's able to do this by inheriting the :class:`~.CacheDataProviderMixin`
and implementing all of its ``abstractmethods``.

So, extending from the previous example we've tackled above to support cache
would lead to the following code:

.. code-block:: python

    import web_poet
    from scrapy_poet.page_input_providers import (
        CacheDataProviderMixin,
        PageObjectInputProvider,
    )

    class HttpResponseProvider(PageObjectInputProvider, CacheDataProviderMixin):
        """This class provides ``web_poet.HttpResponse`` instances."""
        provided_classes = {web_poet.HttpResponse}

        def __call__(self, to_provide: Set[Callable], response: Response):
            """Build a ``web_poet.HttpResponse`` instance using a Scrapy ``Response``"""
            return [
                web_poet.HttpResponse(
                    url=response.url,
                    body=response.body,
                    status=response.status,
                    headers=web_poet.HttpResponseHeaders.from_bytes_dict(response.headers),
                )
            ]

        def fingerprint(self, to_provide: Set[Callable], request: Request) -> str:
            """Returns a fingerprint to identify the specific request."""
            # Implementation here

        def serialize(self, result: Sequence[Any]) -> Any:
            """Serializes the results of this provider. The data returned will
            be pickled.
            """
            # Implementation here

        def deserialize(self, data: Any) -> Sequence[Any]:
            """Deserialize some results of the provider that were previously
            serialized using the serialize() method.
            """
            # Implementation here

Take note that even if you're using providers that supports the Caching interface,
it's only going to be used if the ``SCRAPY_POET_CACHE`` has been enabled in the
settings.

The caching of provided dependencies is **very useful for local development** of
Page Objects, as it lowers down the waiting time for your Responses `(or any type
of external dependency for that manner)` by caching them up locally.

Currently, the data is cached using a sqlite database in your local directory.
This is implemented using :class:`~.SqlitedictCache`.

The cache mechanism that ``scrapy-poet`` currently offers is quite different
from the :class:`~.scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware`
which Scrapy has. Although they are quite similar in its intended purpose,
``scrapy-poet``'s cached data is directly tied to its appropriate provider. This
could be anything that could stretch beyond Scrapy's ``Responses`` `(e.g. Network
Database queries, API Calls, AWS S3 files, etc)`.


Configuring providers
=====================

The list of available providers should be configured in the spider settings. For example,
the following configuration should be included in the settings to enable a new provider
``MyProvider``:

.. code-block:: python

    "SCRAPY_POET_PROVIDERS": {MyProvider: 500}

The number used as value (`500`) defines the provider priority. See
:ref:`Scrapy Middlewares <scrapy:topics-downloader-middleware-ref>`
configuration dictionaries for more information.

.. note::

    The providers in :const:`scrapy_poet.DEFAULT_PROVIDERS`,
    which includes a provider for :class:`~HttpResponse`, are always
    included by default. You can disable any of them by listing it
    in the configuration with the priority `None`.

Ignoring requests
=================

Sometimes requests could be skipped, for example, when you're fetching data
using a third-party API such as Auto Extract or querying a database.

In cases like that, it makes no sense to send the request to Scrapy's downloader
as it will only waste network resources. But there's an alternative to avoid
making such requests, you could use :class:`~.DummyResponse` type to annotate
your response arguments.

That could be done in the spider's parser method:

.. code-block:: python

    def parser(self, response: DummyResponse, page: MyPageObject):
        pass

Spider method that has its first argument annotated as :class:`~.DummyResponse`
is signaling that it is not going to use the response, so it should be safe
to not download scrapy Response as usual.

This type annotation is already applied when you use the :func:`~.callback_for`
helper: the callback which is created by ``callback_for`` doesn't use Response,
it just calls page object's ``to_item`` method.

If neither spider callback nor any of the input providers are using
``Response``, :class:`~.InjectionMiddleware` skips the download, returning a
:class:`~.DummyResponse` instead. For example:

.. code-block:: python

    def get_cached_content(key: str):
        # get cached html response from db or other source
        pass


    @attr.define
    class CachedData:
        key: str
        value: str


    class CachedDataProvider(PageObjectInputProvider):
        provided_classes = {CachedData}

        def __call__(self, to_provide: List[Callable], request: scrapy.Request):
            return [
                CachedData(
                    key=request.url,
                    value=get_cached_content(request.url)
                )
            ]


    @attr.define
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

Although, if the spider callback is not using ``Response``, but the
Page Object uses it, the request is not ignored, for example:

.. code-block:: python

    def parse_content(html: str):
        # parse content from html
        pass


    @attr.define
    class MyResponseData:
        url: str
        html: str


    class MyResponseDataProvider(PageObjectInputProvider):
        provided_classes = {MyResponseData}

        def __call__(self, to_provide: Set[Callable], response: Response):
            return [
                MyResponseData(
                    url=response.url,
                    html=response.content,
                )
            ]


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
    instances in your Page Objects, use built-in ``ItemWebPage`` - it has
    ``response`` attribute with ``HttpResponse``; no additional configuration
    is needed, as there is ``HttpResponseProvider`` enabled in ``scrapy-poet``
    by default.

Requests concurrency
--------------------

DummyRequests are meant to skip downloads, so it makes sense not checking for
concurrent requests, delays, or auto throttle settings since we won't be making
any download at all.

By default, if your parser or its page inputs need a regular Request,
this request is downloaded through Scrapy, and all the settings and limits are
respected, for example:

- ``CONCURRENT_REQUESTS``
- ``CONCURRENT_REQUESTS_PER_DOMAIN``
- ``CONCURRENT_REQUESTS_PER_IP``
- ``RANDOMIZE_DOWNLOAD_DELAY``
- all AutoThrottle settings
- ``DownloaderAwarePriorityQueue`` logic

But be aware when using third-party libraries to acquire content for a page
object. If you make an HTTP request in a provider using some third-party async
library (aiohttp, treq, etc.), ``CONCURRENT_REQUESTS`` option will be respected,
but not the others.

To have other settings respected, in addition to ``CONCURRENT_REQUESTS``, you'd
need to use ``crawler.engine.download`` or something like that. Alternatively,
you could implement those limits in the library itself.
