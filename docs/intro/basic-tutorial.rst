.. _`intro-basic-tutorial`:

==============
Basic Tutorial
==============

In this tutorial, we’ll assume that ``scrapy-poet`` is already installed on your
system. If that’s not the case, see :ref:`intro-install`.

.. note::

    This tutorial can be followed without reading `web-poet`_ docs, but
    for a better understanding it is highly recommended to check them first.


We are going to scrape `books.toscrape.com <http://books.toscrape.com/>`_,
a website that lists books from famous authors.

This tutorial will walk you through these tasks:

#. Writing a :ref:`spider <scrapy:topics-spiders>` to crawl a site and extract data
#. Separating extraction logic from the spider
#. Configuring Scrapy project to use ``scrapy-poet``
#. Changing spider to make use of our extraction logic

If you're not already familiar with Scrapy, and want to learn it quickly,
the `Scrapy Tutorial`_ is a good resource.

.. _web-poet: https://web-poet.readthedocs.io/en/stable/

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

To use ``scrapy-poet``, enable its downloader middleware in ``settings.py``:

.. code-block:: python

    DOWNLOADER_MIDDLEWARES = {
        'scrapy_poet.InjectionMiddleware': 543,
    }


``BookPage`` class we created previously can be used without ``scrapy-poet``,
and even without Scrapy (note that imports were from ``web_poet`` so far).

``scrapy-poet`` makes it easy to use `web-poet`_ Page Objects
(such as ``BookPage``) in Scrapy spiders.

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
called ``book_page``. ``scrapy-poet`` detects this and makes sure
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

.. tip::

    :func:`~.callback_for` also supports `async generators`. So if we have the
    following:

    .. code-block:: python

        class BooksSpider(scrapy.Spider):
            name = 'books'
            start_urls = ['http://books.toscrape.com/']

            def parse(self, response):
                links = response.css('.image_container a')
                yield from response.follow_all(links, self.parse_book)

            async def parse_book(self, response: DummyResponse, page: BookPage):
                yield await page.to_item()

    It could be turned into:

    .. code-block:: python

        class BooksSpider(scrapy.Spider):
            name = 'books'
            start_urls = ['http://books.toscrape.com/']

            def parse(self, response):
                links = response.css('.image_container a')
                yield from response.follow_all(links, self.parse_book)

            parse_book = callback_for(BookPage)

    This is useful when the Page Objects uses additional requests, which rely
    heavily on ``async/await`` syntax. More info on this in this tutorial 
    section: :ref:`intro-additional-requests`.

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
This is exactly the functionality that *overrides* provides.

Note that the crawling logic of the ``BooksSpider`` is pretty simple and straightforward:

1. Extract all books URLs from the listing page
2. For each book URL found in the step 1, fetch the page and extract the resultant item

This logic should work without any change for different books sites because
having pages with lists of books and then detail pages with the individual book is
such a common way of structuring sites.

Let's refactor the spider presented in the former section so that it also supports
extracting books from the page `bookpage.com/reviews <https://bookpage.com/reviews>`_
as well.

The steps to follow are:

#. Make our spider generic: move the remaining extraction code from the spider to a Page Object
#. Configure *overrides* for Books to Scrape
#. Add support for another site (Book Page site)

Making the spider generic
-------------------------
This is almost done. The book extraction logic has been already moved to the
``BookPage`` Page Object, but extraction logic to obtain the list of URL to books
is already present in the ``parse`` method. It must be moved to its own Page
Object:

.. code-block:: python

    from web_poet.pages import WebPage


    class BookListPage(WebPage):

        def book_urls(self):
            return self.css('.image_container a')

Let's adapt the spider to use this new Page Object:

.. code-block:: python

    class BooksSpider(scrapy.Spider):
        name = 'books_spider'
        start_urls = ['http://books.toscrape.com/']
        parse_book = callback_for(BookPage)  # extract items from book pages

        def parse(self, response, page: BookListPage):
            yield from response.follow_all(page.book_urls(), self.parse_book)

All the extraction logic that is specific to the site is now responsibility
of the Page Objects. As a result, the spider is now *site-agnostic* and will
work providing that the Page Objects do their work.

In fact, the spider only responsibility becomes expressing the crawling strategy:
"fetch a list of item URLs, follow them, and extract the resultant items".
The code gets clearer and simpler.

Configure *overrides* for Books to Scrape
-----------------------------------------
It is convenient to create bases classes for the Page Objects given that we are going
to have several implementations of the same Page Object (one per each site).
The following code snippet introduces such base classes and refactors the
existing Page Objects as subclasses of them:

.. code-block:: python

    from web_poet.pages import ItemWebPage, WebPage


    # ------ Base page objects ------

    class BookListPage(WebPage):

        def book_urls(self):
            return []


    class BookPage(ItemWebPage):

        def to_item(self):
            return None

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
is using the new base Page Objects and they are empty.
Let's fix it by instructing ``scrapy-poet`` to use the Books To Scrape (BTS)
Page Objects for URLs belonging to the domain ``toscrape.com``. This must
be done by configuring ``SCRAPY_POET_OVERRIDES`` into ``settings.py``:

.. code-block:: python

    "SCRAPY_POET_OVERRIDES": [
        ("toscrape.com", BTSBookListPage, BookListPage),
        ("toscrape.com", BTSBookPage, BookPage)
    ]

The spider is back to life!
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

We cannot reuse the Books to Scrape Page Objects in this case. The site is
different so their extraction logic wouldn't work. Therefore, we have
to implement new ones:

.. code-block:: python

    from web_poet.pages import ItemWebPage, WebPage


    class BPBookListPage(WebPage):

        def book_urls(self):
            return self.css('article.post h4 a::attr(href)').getall()


    class BPBookPage(ItemWebPage):

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("body div > h1::text").get().strip(),
            }

The last step is configuring the overrides so that these new Page Objects
are used for the domain
``bookpage.com``. This is how ``SCRAPY_POET_OVERRIDES`` should look like into
``settings.py``:

.. code-block:: python

    "SCRAPY_POET_OVERRIDES": [
        ("toscrape.com", BTSBookListPage, BookListPage),
        ("toscrape.com", BTSBookPage, BookPage),
        ("bookpage.com", BPBookListPage, BookListPage),
        ("bookpage.com", BPBookPage, BookPage)
    ]

The spider is now ready to extract books from both sites 😀.
The full example
`can be seen here <https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders/books_04_overrides_02.py>`_

On the surface, it looks just like a different way to organize Scrapy spider
code - and indeed, it *is* just a different way to organize the code,
but it opens some cool possibilities.

In the examples above we have been configuring the overrides
for a particular domain, but more complex URL patterns are also possible.
For example, the pattern ``books.toscrape.com/cataloge/category/``
is accepted and it would restrict the override only to category pages.

It is even possible to configure more complex patterns by using the
:py:class:`web_poet.overrides.OverrideRule` class instead of a triplet in
the configuration. Another way of declaring the earlier config
for ``SCRAPY_POET_OVERRIDES`` would be the following:

.. code-block:: python

    from url_matcher import Patterns
    from web_poet import OverrideRule


    SCRAPY_POET_OVERRIDES = [
        OverrideRule(for_patterns=Patterns(["toscrape.com"]), use=BTSBookListPage, instead_of=BookListPage),
        OverrideRule(for_patterns=Patterns(["toscrape.com"]), use=BTSBookPage, instead_of=BookPage),
        OverrideRule(for_patterns=Patterns(["bookpage.com"]), use=BPBookListPage, instead_of=BookListPage),
        OverrideRule(for_patterns=Patterns(["bookpage.com"]), use=BPBookPage, instead_of=BookPage),
    ]

As you can see, this could get verbose. The earlier tuple config simply offers
a shortcut to be more concise.

.. note::

    Also see the `url-matcher <https://url-matcher.readthedocs.io/en/stable/>`_
    documentation for more information about the patterns syntax.

Manually defining overrides like this would be inconvenient, most
especially for larger projects. Fortunately, `web-poet`_ has a cool feature to
annotate Page Objects like :py:func:`web_poet.handle_urls` that would define
and store the :py:class:`web_poet.overrides.OverrideRule` for you. All of the
:py:class:`web_poet.overrides.OverrideRule` rules could then be simply read as:

.. code:: python

    from web_poet import default_registry, consume_modules

    # The consume_modules() must be called first if you need to properly import
    # rules from other packages. Otherwise, it can be omitted.
    # More info about this caveat on web-poet docs.
    consume_modules("external_package_A", "another_ext_package.lib")
    SCRAPY_POET_OVERRIDES = default_registry.get_overrides()

For more info on this, you can refer to these docs:

    * ``scrapy-poet``'s :ref:`overrides` Tutorial section.
    * External `web-poet`_ docs.

        * Specifically, the :external:ref:`intro-overrides` Tutorial section.

Next steps
==========

Now that you know how ``scrapy-poet`` is supposed to work, what about trying to
apply it to an existing or new Scrapy project?

Also, please check the :ref:`overrides` and :ref:`providers` sections as well as
refer to spiders in the "example" folder: https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

.. _Scrapy Tutorial: https://docs.scrapy.org/en/latest/intro/tutorial.html
