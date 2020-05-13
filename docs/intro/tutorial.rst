.. _`intro-tutorial`:

========
Tutorial
========

In this tutorial, we’ll assume that scrapy-poet is already installed on your
system. If that’s not the case, see :ref:`intro-install`.

We are going to scrape `books.toscrape.com <http://books.toscrape.com/>`_,
a website that lists books from famous authors.

This tutorial will walk you through these tasks:

#. Writing a :ref:`spider <scrapy:topics-spiders>` to crawl a site and extract data
#. Separating extraction logic from the spider
#. Configuring Scrapy project to use scrapy-poet
#. Changing spider to make use of our extraction logic

If you're not already familiar with Scrapy, and want to learn it quickly,
the `Scrapy Tutorial`_ is a good resource.

Creating a spider
=================

Create a new Scrapy project and add a new spider to it. This spider will be
called ``books`` and it will crawl and extract data from a target website.

.. code-block:: python

    import scrapy


    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response):
            """Discover book links and follow them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

        def parse_book(self, response):
            """Extract data from book pages"""
            yield {
                'url': response.url,
                'name': response.css("title::text").get(),
            }

Separating extraction logic
===========================

Let's create our first Page Object by moving extraction logic
out of the spider class.

.. code-block:: python

    from web_poet.pages import ItemWebPage


    class BookPage(ItemWebPage):
        """Individual book page on books.toscrape.com website, e.g.
        http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
        """

        def to_item(self):
            """Convert page into an item"""
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }

Now we have a ``BookPage`` class that implements the ``to_item`` method.
This class contains all logic necessary for extracting an item from
an individual book page like
http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html,
and nothing else.

If we want, we can organize code in a different way, and e.g.
extract a property from the ``to_item`` method:

.. code-block:: python

    from web_poet.pages import ItemWebPage


    class BookPage(ItemWebPage):
        """Individual book page on books.toscrape.com website"""

        @property
        def title(self):
            """Book page title"""
            return self.css("title::text").get()

        def to_item(self):
            return {
                'url': self.url,
                'name': self.title,
            }

Configuring the project
=======================

To use scrapy-poet, enable its downloader middleware in ``settings.py``:

.. code-block:: python

    DOWNLOADER_MIDDLEWARES = {
        'scrapy_poet.InjectionMiddleware': 543,
    }


BookPage class we created previously can be used without scrapy-poet,
and even without Scrapy (note that imports were from ``web_poet`` so far).

``scrapy-poet`` makes it easy to use ``web-poet`` Page Objects
(such as BookPage) in Scrapy spiders.

Changing spider
===============

To use the newly created BookPage class in the spider, change
the ``parse_book`` method as follows:

.. code-block:: python

    class BooksSpider(scrapy.Spider):
        # ...
        def parse_book(self, response, book_page: BookPage):
            """Extract data from book pages"""
            yield book_page.to_item()

``parse_book`` method now has a type annotated argument
called ``book_page``. scrapy-poet detects this and makes sure
a BookPage instance is created and passed to the callback.

The full spider code would be looking like this:

.. code-block:: python

    import scrapy


    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response):
            """Discover book links and follow them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

        def parse_book(self, response, book_page: BookPage):
            """Extract data from book pages"""
            yield book_page.to_item()


You might have noticed that ``parse_book`` is quite simple; it's just
returning the result of the ``to_item`` method call. We could use
:func:`~.callback_for` helper to reduce the boilerplate.

.. code-block:: python

    import scrapy
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


.. note::

    You can also write something like
    ``response.follow_all(links, callback_for(BookPage))``, without creating
    an attribute, but currently it won't work with Scrapy disk queues.

Final result
============

At the end of our job, the spider should look like this:

.. code-block:: python

    import scrapy
    from web_poet.pages import ItemWebPage
    from scrapy_poet import callback_for


    class BookPage(ItemWebPage):
        """Individual book page on books.toscrape.com website, e.g.
        http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
        """

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }


    class BooksSpider(scrapy.Spider):
        """Crawl and extract books data"""

        name = 'books'
        start_urls = ['http://books.toscrape.com/']
        parse_book = callback_for(BookPage)  # extract items from book pages

        def parse(self, response):
            """Discover book links and follow them"""
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)


It now looks similar to the original spider, but the item extraction logic
is separated from the spider.

On a surface, it looks just like a different way to organize Scrapy spider
code - and indeed, it *is* just a different way to organize the code,
but it opens some cool possibilities.

Next steps
==========

Now that you know how scrapy-poet is supposed to work, what about trying to
apply it to an existing or new Scrapy project?

Also, please check :ref:`advanced` and refer to spiders in the "example"
folder: https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

.. _Scrapy Tutorial: https://docs.scrapy.org/en/latest/intro/tutorial.html
