.. _`intro-tutorial`:

========
Tutorial
========

In this tutorial, we’ll assume that scrapy-poet is already installed on your
system. If that’s not the case, see :ref:`intro-install`.

.. note::

    This tutorial can be followed without reading `web-poet docs`_, but
    for a better understanding it is highly recommended to check them first.


We are going to scrape `books.toscrape.com <http://books.toscrape.com/>`_,
a website that lists books from famous authors.

This tutorial will walk you through these tasks:

#. Writing a :ref:`spider <scrapy:topics-spiders>` to crawl a site and extract data
#. Separating extraction logic from the spider
#. Configuring Scrapy project to use scrapy-poet
#. Changing spider to make use of our extraction logic

If you're not already familiar with Scrapy, and want to learn it quickly,
the `Scrapy Tutorial`_ is a good resource.

.. _web-poet docs: https://web-poet.readthedocs.io/en/latest/

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
In particular, ``BookPage`` is now independent of Scrapy,
and is not doing any I/O.

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


``BookPage`` class we created previously can be used without scrapy-poet,
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

Single spider - multiple sites
==============================

We have seen that using Page Objects is a great way to isolate the extraction logic
from the crawling logic.
As a side effect, it is now pretty easy to **create a generic spider with a common crawling logic
that works across different sites**. The unique missing requirement is to be able to
configure different Page Objects for different sites, because the extraction logic
surely changes from site to site.
This is exactly the functionality that overrides provides.

Note that the crawling logic of the ``BooksSpider`` is pretty simple and straightforward:

1. Extract all books URLs from the listing page
2. For each book URL found in the step 1, fetch the page and extract the resultant item

This logic should work without any change for different books sites because
having pages with lists of books and then detail pages with the individual book is
such a common way of structuring sites.

Let's refactor the spider presented in the former section so that it also supports
extracting books from the page `bookpage.com/reviews <https://bookpage.com/reviews>`_.

The steps will follow are:

#. Make the spider generic: create a Page Object for the listing extraction
#. Introduce overrides for Books to Scrape
#. Add support for another site (Book Page site)

Making the spider generic
-------------------------
This is almost done. The book extraction logic has been already moved to the
``BookPage`` Page Object, but extraction logic to obtain the list of URL to books
is already present in the ``parse`` method. It must be moved to its own Page
Object:

.. code-block:: python

    class BookListPage(WebPage):

        def book_urls(self):
            return self.css('.article-info a::attr(href)').getall()

Let's adapt the spider to use this new Page Object:

.. code-block:: python

    class BooksSpider(scrapy.Spider):
        name = 'books_spider'
        start_urls = ['http://books.toscrape.com/']
        parse_book = callback_for(BookPage)  # extract items from book pages

        def parse(self, response, page: BookListPage):
            yield from response.follow_all(page.books_urls(), self.parse_book)

All the extraction logic that is specific to each site is now responsibility
of the Page Objects. As result, the spider is generic and will work providing that the
Page Objects do their work.

Introduce overrides for Books to Scrape
---------------------------------------
It is convenient to create bases classes for the Page Objects given that we are going
to have several implementations of the same Page Objects (one per each site).
The following code snippet introduces such base classes:

.. code-block:: python

    # ------ Base page objects ------

    class BookListPage(WebPage):

        def book_urls(self):
            return []


    class BookPage(ItemWebPage):

        def to_item(self):
            return {}

    # ------ Concrete page objects for books.toscrape.com (BTS) ------

    class BTSBookListPage(BookListPage):

        def book_urls(self):
            return self.css('.image_container a::attr(href)').getall()


    class BTSBookPage(BookPage):

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }

The spider won't work anymore after the change. The reason is that it
is using the empty base page objects without any logic. Let's fix that
by configuring the overrides for the ``toscrape.com`` domain
in ``settings.py``:

.. code-block:: python

    SCRAPY_POET_OVERRIDES = {
        "toscrape.com": {
            BookListPage: BTSBookListPage,
            BookPage: BTSBookPage
        }
    }

The spider is back to live!
``SCRAPY_POET_OVERRIDES`` contain rules that overrides the Page Objects
used for a particular domain. In this particular case, Page Objects
``BTSBookListPage`` and ``BTSBookPage`` will be used instead of
``BookListPage`` and ``BookPage`` for any request whose domain is
``toscrape.com``.

The right Page Objects will be then injected
in the spider callbacks whenever a URL that belongs to the domain ``toscrape.com``
is requested.

Add another site
----------------
The code is now refactored to accept other implementations for other sites.
Let's illustrate it by adding support for the books in the
page `bookpage.com/reviews <https://bookpage.com/reviews>`_.

We cannot reuse the Books to Scrape Page Objects in this case, so we have
to implement new ones:

.. code-block:: python

    class BPBookListPage(WebPage):

        def book_urls(self):
            return self.css('.article-info a::attr(href)').getall()


    class BPBookPage(ItemWebPage):

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css(".book-data h4::text").get().strip(),
            }

The last step is configuring the Page Objects to be used for the domain
``bookpage.com`` in the settings property ``SCRAPY_POET_OVERRIDES``.

.. code-block:: python

    SCRAPY_POET_OVERRIDES = {
        "toscrape.com": {
            BookListPage: BTSBookListPage,
            BookPage: BTSBookPage
        },
        "bookpage.com": {
            BookListPage: BPBookListPage,
            BookPage: BPBookPage
        }
    }

The spider is now ready to extract books from both sites 😀.
The full example
`can be seen here <https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders/books_04_overrides_02.py>`_

On a surface, it looks just like a different way to organize Scrapy spider
code - and indeed, it *is* just a different way to organize the code,
but it opens some cool possibilities.

Next steps
==========

Now that you know how scrapy-poet is supposed to work, what about trying to
apply it to an existing or new Scrapy project?

Also, please check :ref:`overrides`, :ref:`providers` and refer to spiders in the "example"
folder: https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

.. _Scrapy Tutorial: https://docs.scrapy.org/en/latest/intro/tutorial.html
