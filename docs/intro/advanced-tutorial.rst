.. _`intro-advanced-tutorial`:

=================
Advanced Tutorial
=================

This section intends to go over the supported features in **web-poet** by
**scrapy-poet**:

    * ``web_poet.HttpClient``
    * ``web_poet.Meta``

These are mainly achieved by **scrapy-poet** implementing **providers** for them:

    * :class:`scrapy_poet.page_input_providers.HttpClientProvider`
    * :class:`scrapy_poet.page_input_providers.MetaProvider`

.. _`intro-additional-requests`:

Additional Requests
===================

Using Page Objects using additional requests doesn't need anything special from
the spider. It would work as-is because of the readily available 
:class:`scrapy_poet.page_input_providers.HttpClientProvider` that is enabled
out of the box.

This supplies the Page Object with the necessary ``web_poet.HttpClient`` instance.
Take note the HTTP Downloader implementation that **scrapy-poet** provides to
``web_poet.HttpClient`` would be the **Scrapy Downloader**.

.. tip::

    This means that the additional requests inside a Page Object will have access
    to the **Downloader Middlewares** that the Spider is using.


Suppose we have the following Page Object:

.. code-block:: python

    import attr
    import web_poet


    @attr.define
    class ProductPage(web_poet.ItemWebPage):
        http_client: web_poet.HttpClient

        async def to_item(self):
            item = {
                "url": self.url,
                "name": self.css("#main h3.name ::text").get(),
                "product_id": self.css("#product ::attr(product-id)").get(),
            }

            # Simulates clicking on a button that says "View All Images"
            response: web_poet.HttpResponse = await self.http_client.get(
                f"https://api.example.com/v2/images?id={item['product_id']}"
            )
            item["images"] = response.css(".product-images img::attr(src)").getall()
            return item


It can be directly used inside the spider as:

.. code-block:: python

    import scrapy


    def ProductSpider(scrapy.Spider):

        custom_settings = {
            "DOWNLOADER_MIDDLEWARES": {
                "scrapy_poet.InjectionMiddleware": 543,
            }
        }

        start_urls = [
            "https://example.com/category/product/item?id=123",
            "https://example.com/category/product/item?id=989",
        ]

        async def parse(self, response, page: ProductPage):
            return await page.to_item()

Note that we needed to update the ``parse()`` method to be an ``async`` method,
since the ``to_item()`` method of the Page Object we're using is an ``async``
method as well.

This is also the primary reason why **scrapy-poet** requires ``scrapy>=2.6.0``
since it's the minimum version that has full :mod:`asyncio` support.


Meta
====

Using ``web_poet.Meta`` allows the Scrapy spider to pass any arbitrary information
into the Page Object.

Suppose we update the earlier Page Object to control the additional request.
This basically acts as a switch to update the behavior of the Page Object:

.. code-block:: python

    import attr
    import web_poet


    @attr.define
    class ProductPage(web_poet.ItemWebPage):
        http_client: web_poet.HttpClient
        meta: web_poet.Meta

        async def to_item(self):
            item = {
                "url": self.url,
                "name": self.css("#main h3.name ::text").get(),
                "product_id": self.css("#product ::attr(product-id)").get(),
            }

            # Simulates clicking on a button that says "View All Images"
            if self.meta.get("enable_extracting_all_images")
                response: web_poet.HttpResponse = await self.http_client.get(
                    f"https://api.example.com/v2/images?id={item['product_id']}"
                )
                item["images"] = response.css(".product-images img::attr(src)").getall()

            return item

Passing the ``enable_extracting_all_images`` meta value from the spider into
the Page Object can be achieved by using **Scrapy's** ``Request.meta`` attribute.
Specifically, any ``dict`` value inside the ``po_args`` parameter inside
**Scrapy's** ``Request.meta`` will be passed into ``web_poet.Meta``.

Let's see it in action:

.. code-block:: python

    import scrapy


    def ProductSpider(scrapy.Spider):

        custom_settings = {
            "DOWNLOADER_MIDDLEWARES": {
                "scrapy_poet.InjectionMiddleware": 543,
            }
        }

        start_urls = [
            "https://example.com/category/product/item?id=123",
            "https://example.com/category/product/item?id=989",
        ]

        def start_requests(self):
            for url in start_urls:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={"po_args": {"enable_extracting_all_images": True}}
                )

        async def parse(self, response, page: ProductPage):
            return await page.to_item()
