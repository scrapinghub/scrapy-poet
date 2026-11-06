.. _pitfalls:

========
Pitfalls
========

``scrapy.Request`` without callback
===================================

Like Scrapy, scrapy-poet treats a :class:`scrapy.Request
<scrapy.http.Request>` whose callback is ``None`` as a request for the
``parse()`` method of the spider: it builds the dependencies of that method,
and skips the download if its response parameter is annotated with
:class:`~.DummyResponse`.

So, if you send requests directly to the downloader, set their callback to
:func:`scrapy.http.request.NO_CALLBACK` instead of ``None``.

Opening a response in a web browser
===================================

When using scrapy-poet, the ``open_in_browser`` function from Scrapy may raise
the following exception::

    TypeError: Unsupported response type: HttpResponse

To avoid that, use the ``open_in_browser`` function from ``scrapy_poet.utils``
instead:

.. code-block:: python

    from scrapy_poet.utils import open_in_browser
