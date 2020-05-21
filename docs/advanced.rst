.. _`advanced`:

==============
Advanced Usage
==============

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

Currently, scrapy-poet is able to inject instances of the following
classes as *provider* dependencies:

- :class:`~scrapy.http.Request`
- :class:`~scrapy.http.Response`
- :class:`~scrapy.settings.Settings`

.. warning::

    If your provider needs to use a subclass of Response,
    for example, TextResponse,
    make sure to annotate your response argument with the parent class type.

    Our dependency injection strategy respects covariance.
    In simple words,
    this means a subclass could replace a parent class
    but a parent class could not substitute its subclasses.
    Example:

    .. code-block:: python

        class Animal:
            pass

        class Cat(Animal):
            def meow(self):
                pass

    If our provider needs an Animal instance,
    we could provide either an Animal or a Cat
    (a more specific Animal subtype).
    On the other hand,
    if our provider needs a Cat instance
    (probably because meow is a requirement),
    it wouldn't be okay to pass it an Animal instance.

    Our Injection Middleware makes no distinction between Responses and TextResponses,
    so you need to validate the response type by yourself.
    Example:

    .. code-block:: python

        @provides(MyCustomResponseData)
        class MyCustomResponseDataProvider(PageObjectInputProvider):

            def __init__(self, response: Response):
                assert issubclass(response, TextResponse)
                self.response = response

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

    def parser(self, response: DummyRequest, page: MyPageObject):
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


    @provides(CachedData)
    class CachedDataProvider(PageObjectInputProvider):

        def __init__(self, request: scrapy.Request):
            self.request = request

        def __call__(self):
            return CachedData(
                key=self.request.url,
                value=get_cached_content(self.request.url)
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
