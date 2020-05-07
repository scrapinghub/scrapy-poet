.. _`intro-tutorial`:

========
Tutorial
========

In this tutorial, we’ll assume that scrapy-poet is already installed on your
system. If that’s not the case, see :ref:`intro-install`.

We are going to scrape `books.toscrape.com <http://books.toscrape.com/>`_,
a website that lists books from famous authors.

This tutorial will walk you through these tasks:

1. Writing a :ref:`spider <scrapy:topics-spiders>` to crawl a site and extract data
2. Configuring Scrapy project to include Injection Middleware
3. Separating extraction logic from spider
4. Changing spider to make use of our extraction logic

If you're not already familiar with Scrapy, and want to learn it quickly,
the `Scrapy Tutorial`_ is a good resource.

Creating a spider
=================

Create a new Scrapy project and add a new spider to it. This spider will be
called ``books`` and it will crawl and extract data from our target website.

.. code-block:: python

    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response):
            """Discovers book links and follows them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

        def parse_book(self, response):
            """Extract data from book pages"""
            yield {
                'url': response.url,
                'name': response.css("title::text").get(),
            }

Configuring the project
=======================

We need to enable our custom downloader middleware in ``settings.py``.
It's a fundamental part of scrapy-poet as it makes dependency injection possible
(among other things).

.. code-block:: python

    DOWNLOADER_MIDDLEWARES = {
       'scrapy_poet.InjectionMiddleware': 543,
    }

Separating extraction logic
===========================

Let's create our first Page Object abstraction by moving extraction logic
outside our spider file.

.. code-block:: python

    from web_poet.pages import ItemWebPage


    class BookPage(ItemWebPage):
        """Individual book page on books.toscrape.com website, e.g.
        http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
        """

        def to_item(self):
            """Converts page into an item"""
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }

Now we have a ``BookPage`` class that implements the ``to_item`` method.
We could go even further and extract a property from the ``to_item`` method.

.. code-block:: python

    from web_poet.pages import ItemWebPage


    class BookPage(ItemWebPage):
        """Extracts data from a book page"""

        @property
        def title(self):
            """Extracts title from book page"""
            return self.css("title::text").get()

        def to_item(self):
            """Converts page into an item"""
            return {
                'url': self.url,
                'name': self.title,
            }

Changing spider
===============

The next step is to change our ``parse_book`` method in order to consume our
newly created Page Object class.

.. code-block:: python

    def parse_book(self, response, book_page: BookPage):
        """Extract data from book pages"""
        yield book_page.to_item()

The parser method now receives a type annotated argument called ``book_page``.
Our Injection Middleware will detect it and provide the required dependencies.

The spider should be looking like this:

.. code-block:: python

    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response):
            """Discovers book links and follows them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

        def parse_book(self, response, book_page: BookPage):
            """Extract data from book pages"""
            yield book_page.to_item()

You might have noticed that our parser method is quite simples and it's just
returning the result of the ``to_item`` method call. We could make use of the
``callback_for`` helper to reduce source code here.

.. code-block:: python

    from scrapy_poet import callback_for


    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']
        parse_book = callback_for(BookPage)

        def parse(self, response):
            """Discovers book links and follows them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

This helper could be used as an inline callback, but it would not work with
disk-based request queues. To be safe, we're defining it as an attribute.

Final result
============

At the end of our job, our spider should look like this:

.. code-block:: python

    import scrapy

    from scrapy_poet import callback_for
    from web_poet.pages import ItemWebPage


    class BookPage(ItemWebPage):
        """Extracts data from a book page"""

        @property
        def title(self):
            """Extracts title from book page"""
            return self.css("title::text").get()

        def to_item(self):
            """Converts page into an item"""
            return {
                'url': self.url,
                'name': self.title,
            }


    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']
        parse_book = callback_for(BookPage)

        def parse(self, response):
            """Discovers book links and follows them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

Next steps
==========

Now that you know how scrapy-poet is supposed to work, what about trying to
apply it to an existing or new Scrapy project?

Also, please check :ref:`advanced` and refer to spiders in the "example" folder: https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

.. _Scrapy Tutorial: https://docs.scrapy.org/en/latest/intro/tutorial.html
