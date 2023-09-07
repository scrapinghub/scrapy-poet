.. _pitfalls:

========
Pitfalls
========

``scrapy.Request`` without callback
===================================

.. tip::

    Note that the pitfalls discussed in this section aren't applicable to
    Scrapy >= 2.8 for most cases.

    However, if you have code somewhere which directly adds 
    :class:`scrapy.Request <scrapy.http.Request>` instances to the downloader,
    you need to ensure that they don't use ``None`` as the callback value.
    Instead, you can use the new :func:`scrapy.http.request.NO_CALLBACK`
    value introduced in Scrapy 2.8.

.. note::

    This section *only applies* to specific cases where spiders define a
    ``parse()`` method.

    The TLDR; recommendation is to simply avoid defining a ``parse()`` method
    and instead choose another name.

Scrapy supports declaring :class:`scrapy.Request <scrapy.http.Request>` instances
without setting any callbacks (i.e. ``None``). For these instances, Scrapy uses
the ``parse()`` method as its callback.

Let's take a look at the following code:

.. code-block:: python

    import scrapy


    class MySpider(scrapy.Spider):
        name = "my_spider"
        start_urls = ["https://books.toscrape.com"]

        def parse(self, response):
            ...

Under the hood, the inherited ``start_requests()`` method from
:class:`scrapy.Spider <scrapy.spiders.Spider>` doesn't declare any callback
value to :class:`scrapy.Request <scrapy.http.Request>`:

.. code-block:: python

    for url in self.start_urls:
        yield Request(url, dont_filter=True)

Apart from this, there are also some built-in Scrapy < 2.8 features which omit
the :class:`scrapy.Request <scrapy.http.Request>` callback value:

* :class:`scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware`
* :class:`scrapy.pipelines.images.ImagesPipeline`
* :class:`scrapy.pipelines.files.FilesPipeline`

However, omitting the :class:`scrapy.Request <scrapy.http.Request>` callback
value presents *some problems* for **scrapy-poet**. 

Skipped Downloads
-----------------

.. note::

    This subsection is specific to cases wherein a
    :class:`~.DummyResponse` annotates the response in a ``parse()``
    method.

Let's take a look at an example:

.. code-block:: python

    import scrapy
    from scrapy_poet import DummyResponse


    class MySpider(scrapy.Spider):
        name = "my_spider"
        start_urls = ["https://books.toscrape.com"]

        def parse(self, response: DummyResponse):
            ...

In order for the built-in Scrapy < 2.8 features listed above to work properly,
**scrapy-poet** chooses to ignore the :class:`~.DummyResponse`
annotation completely. This means that the response is downloaded instead of
being skipped.

Otherwise, :class:`scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware`
might not work properly and would **not** visit the ``robots.txt`` file from the
website.

Moreover, this **scrapy-poet** behavior avoids the problem of the images or files
being missing when the following pipelines are used:

* :class:`scrapy.pipelines.images.ImagesPipeline`
* :class:`scrapy.pipelines.files.FilesPipeline`

Note that the following :class:`UserWarning` is emitted when encountering such
scenario:

    A request has been encountered with callback=None which
    defaults to the parse() method. If the parse() method is
    annotated with scrapy_poet.DummyResponse (or its subclasses),
    we're assuming this isn't intended and would simply ignore
    this annotation.

To avoid the said warning and this **scrapy-poet** behavior from occurring, it'd
be best to avoid defining a ``parse()`` method and instead choose any other name.

Dependency Building
-------------------
.. note::

    This subsection is specific to cases wherein dependencies are provided by
    **scrapy-poet** in the ``parse()`` method.

Let's take a look at the following code:

.. code-block:: python

    import attrs
    import scrapy

    from myproject.page_objects import MyPage


    class MySpider(scrapy.Spider):
        name = "my_spider"
        start_urls = ["https://books.toscrape.com"]

        def parse(self, response: scrapy.http.Response, page: MyPage):
            ...

In the above example, this error would be raised: ``TypeError: parse() missing 1
required positional argument: 'page'``. 

The reason for this **scrapy-poet** behavior is to prevent the wasted dependency
building *(which could be expensive in some cases)* when the ``parse()`` method
is unintentionally used.

For example, if a spider is using the :class:`scrapy.pipelines.images.ImagesPipeline`,
**scrapy-poet**'s :class:`scrapy_poet.downloadermiddlewares.InjectionMiddleware`
could be wasting precious compute resources to fulfill one or more dependencies
that won't be used at all. Specifically, the ``page`` argument to the ``parse()``
method is not utilized. If there are a million of images to be downloaded, then
the ``page`` instance is created a million times as well.

The following :class:`UserWarning` is emitted on such scenario:

    A request has been encountered with callback=None which
    defaults to the parse() method. On such cases, annotated
    dependencies in the parse() method won't be built by
    scrapy-poet. However, if the request has callback=parse,
    the annotated dependencies will be built.

As the warning message suggests, this could be fixed by ensuring that the callback
is **not** ``None``:

.. code-block:: python

    class MySpider(scrapy.Spider):
        name = "my_spider"

        def start_requests(self):
            yield scrapy.Request("https://books.toscrape.com", callback=self.parse)

        def parse(self, response: scrapy.http.Response, page: MyPage):
            ...

The :class:`UserWarning` is only shown when the ``parse()`` method declares any
dependency that is fullfilled by any provider declared in ``SCRAPY_POET_PROVIDERS``.
This means that the following code doesn't produce the warning nor attempts to
skip any dependency from being built because there is none:

    .. code-block:: python

        class MySpider(scrapy.Spider):
            name = "my_spider"
            start_urls = ["https://books.toscrape.com"]

            def parse(self, response: scrapy.http.Response):
                ...

Similarly, the best way to completely avoid the said warning and this **scrapy-poet**
behavior is to avoid defining a ``parse()`` method and instead choose any other name.

Open in browser
---------------

When using scrapy-poet, the ``open_in_browser`` function from Scrapy may raise
the following exception:

.. code-block:: python

    TypeError: Unsupported response type: HttpResponse

To avoid that, use the ``open_in_browser`` function from ``scrapy_poet.utils``
instead:

.. code-block:: python

    from scrapy_poet.utils import open_in_browser
