.. _intro-advanced-tutorial:

=================
Advanced Tutorial
=================

This section intends to go over the supported features in **web-poet** by
**scrapy-poet**:

    * :class:`web_poet.HttpClient <web_poet.page_inputs.client.HttpClient>`
    * :class:`web_poet.PageParams <web_poet.page_inputs.page_params.PageParams>`

These are mainly achieved by **scrapy-poet** implementing **providers** for them:

    * :class:`scrapy_poet.HttpClientProvider <scrapy_poet.page_input_providers.HttpClientProvider>`
    * :class:`scrapy_poet.PageParamsProvider <scrapy_poet.page_input_providers.PageParamsProvider>`

.. _intro-additional-requests:

Additional Requests
===================

Using Page Objects using additional requests doesn't need anything special from
the spider. It would work as-is because of the readily available
:class:`scrapy_poet.HttpClientProvider <scrapy_poet.page_input_providers.HttpClientProvider>`
that is enabled out of the box.

This supplies the Page Object with the necessary
:class:`web_poet.HttpClient <web_poet.page_inputs.client.HttpClient>` instance.

The HTTP client implementation that **scrapy-poet** provides to
:class:`web_poet.HttpClient <web_poet.page_inputs.client.HttpClient>` handles
requests as follows:

-   Requests go through downloader middlewares, but they do not go through
    spider middlewares or through the scheduler.

-   Duplicate requests are not filtered out.

-   In line with the web-poet specification for additional requests,
    ``Request.meta["dont_redirect"]`` is set to ``True`` for requests with the
    ``HEAD`` HTTP method.

Suppose we have the following Page Object:

.. code-block:: python

    import attr
    import web_poet


    @attr.define
    class ProductPage(web_poet.WebPage):
        http: web_poet.HttpClient

        async def to_item(self):
            item = {
                "url": self.url,
                "name": self.css("#main h3.name ::text").get(),
                "product_id": self.css("#product ::attr(product-id)").get(),
            }

            # Simulates clicking on a button that says "View All Images"
            response: web_poet.HttpResponse = await self.http.get(
                f"https://api.toscrape.com/v2/images?id={item['product_id']}"
            )
            item["images"] = response.css(".product-images img::attr(src)").getall()
            return item


It can be directly used inside the spider as:

.. code-block:: python

    import scrapy


    class ProductSpider(scrapy.Spider):

        async def start(self):
            for url in [
                "https://toscrape.com/category/product/item?id=123",
                "https://toscrape.com/category/product/item?id=989",
            ]:
                yield scrapy.Request(url, callback=self.parse)

        async def parse(self, response, page: ProductPage):
            return await page.to_item()

Note that we needed to update the ``parse()`` method to be an ``async`` method,
since the ``to_item()`` method of the Page Object we're using is an ``async``
method as well.


Page params
===========

Using :class:`web_poet.PageParams <web_poet.page_inputs.page_params.PageParams>`
allows the Scrapy spider to pass any arbitrary information into the Page Object.

Suppose we update the earlier Page Object to control the additional request.
This basically acts as a switch to update the behavior of the Page Object:

.. code-block:: python

    import attr
    import web_poet


    @attr.define
    class ProductPage(web_poet.WebPage):
        http: web_poet.HttpClient
        page_params: web_poet.PageParams

        async def to_item(self):
            item = {
                "url": self.url,
                "name": self.css("#main h3.name ::text").get(),
                "product_id": self.css("#product ::attr(product-id)").get(),
            }

            # Simulates clicking on a button that says "View All Images"
            if self.page_params.get("enable_extracting_all_images"):
                response: web_poet.HttpResponse = await self.http.get(
                    f"https://api.toscrape.com/v2/images?id={item['product_id']}"
                )
                item["images"] = response.css(".product-images img::attr(src)").getall()

            return item

Passing the ``enable_extracting_all_images`` page parameter from the spider
into the Page Object can be achieved by using
:attr:`scrapy.Request.meta <scrapy.http.Request.meta>` attribute. Specifically,
any ``dict`` value inside the ``page_params`` parameter inside
:attr:`scrapy.Request.meta <scrapy.http.Request.meta>` will be passed into
:class:`web_poet.PageParams <web_poet.page_inputs.page_params.PageParams>`.

Let's see it in action:

.. code-block:: python

    import scrapy


    class ProductSpider(scrapy.Spider):

        start_urls = [
            "https://toscrape.com/category/product/item?id=123",
            "https://toscrape.com/category/product/item?id=989",
        ]

        async def start(self):
            for url in start_urls:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={"page_params": {"enable_extracting_all_images": True}},
                )

        async def parse(self, response, page: ProductPage):
            return await page.to_item()

.. _inline:

Inline page object and item resolution
======================================

The callback-based approach — annotating a ``parse`` method with page object
types — is the recommended pattern for most spiders. Sometimes, however, you
might want to resolve a page object or extract an item *inline*.

:class:`~scrapy_poet.InjectionMiddleware` provides two methods for this:

-   :meth:`~scrapy_poet.InjectionMiddleware.get_page` — downloads a URL and
    returns a page object instance.
-   :meth:`~scrapy_poet.InjectionMiddleware.get_item` — downloads a URL,
    builds the page object, and calls its ``to_item()`` method, returning the
    extracted item directly.

Both methods require **Scrapy 2.14+**. Retrieve the middleware instance via
:meth:`scrapy.crawler.Crawler.get_downloader_middleware`.

.. code-block:: python

    import scrapy
    from scrapy_poet import InjectionMiddleware


    class ProductSpider(scrapy.Spider):
        start_urls = [
            "https://toscrape.com/category/product/item?id=123",
            "https://toscrape.com/category/product/item?id=989",
        ]

        async def start(self):
            mw = self.crawler.get_downloader_middleware(InjectionMiddleware)
            for url in self.start_urls:
                yield await mw.get_item(url, ProductPage)

Both methods accept any of the following as their first argument:

-   A URL string.
-   A :class:`scrapy.Request` — useful when you need to set custom headers,
    meta, or other request options.
-   A :class:`web_poet.HttpRequest`, :class:`web_poet.RequestUrl`, or
    :class:`web_poet.ResponseUrl`.

**Passing page params**

Both methods accept a ``page_params`` keyword argument that is forwarded to
the page object as a :class:`~web_poet.PageParams` dependency, equivalent to
setting ``Request.meta["page_params"]``:

.. code-block:: python

        async def start(self):
            mw = self.crawler.get_downloader_middleware(InjectionMiddleware)
            for url in self.start_urls:
                yield await mw.get_item(url, ProductPage, page_params={"enable_images": True})
