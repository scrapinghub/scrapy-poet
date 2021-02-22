.. _`providers`:

=========
Providers
=========

.. note::

    This document assumes a good familiarity with ``web-poet`` concepts;
    make sure you've read ``web-poet`` docs_.

    This page is mostly aimed at developers who want to extend scrapy-poet,
    not to developers who're writing extraction and crawling code using
    scrapy-poet.


.. _docs: https://web-poet.readthedocs.io/en/stable/

Creating providers
==================

Providers are responsible for building dependencies needed by Injectable
objects. A good example would be the ``ResponseDataProvider``,
which builds and provides a ``ResponseData`` instance for Injectables
that need it, like the ``ItemWebPage``.

.. code-block:: python

    @attr.s(auto_attribs=True)
    class ResponseData:
        """Represents a response containing its URL and HTML content."""
        url: str
        html: str


    class ResponseDataProvider(PageObjectInputProvider):
        """This class provides ``web_poet.page_inputs.ResponseData`` instances."""
        provided_classes = {ResponseData}

        def __call__(self, to_provide: Set[Callable], response: Response):
            """Build a ``ResponseData`` instance using a Scrapy ``Response``"""
            return [ResponseData(url=response.url, html=response.text)]

You can implement your own providers in order to extend or override
current scrapy-poet behavior.
Please, check :class:`scrapy_poet.page_input_providers.PageObjectInputProvider` for more details.

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
    which includes a provider for :class:`~ResponseData`, are always
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


    @attr.s(auto_attribs=True)
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


    @attr.s(auto_attribs=True)
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
    ``response`` attribute with ``ResponseData``; no additional configuration
    is needed, as there is ``ResponseDataProvider`` enabled in scrapy-poet
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
