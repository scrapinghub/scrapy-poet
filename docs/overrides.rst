.. _`overrides`:

=========
Overrides
=========

Using Page Objects is a great way to isolate the extraction logic from the crawling logic.
As a side effect, it is now pretty easy to **create a generic spider with a common crawling logic
that works across different sites**. The unique missing requirement is to be able to
configure different Page Objects for each different site, because the extraction logic
surely changes from site to site.
This is exactly the functionality that overrides provides.

Let's see is with an example. The following is a a spider that extract books
from `books.toscrape.com <http://books.toscrape.com/>`_ using Page Objects.

.. code-block:: python

    import scrapy
    from web_poet import ItemWebPage, WebPage
    from scrapy_poet import callback_for


    class BookListPage(WebPage):

        def book_urls(self):
            return self.css('.image_container a::attr(href)').getall()


    class BookPage(ItemWebPage):

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }


    class BooksSpider(scrapy.Spider):
        name = 'books_spider'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response, page: BookListPage):
            for url in page.book_urls():
                yield response.follow(url, callback_for(BookPage))

Note that the crawling logic is pretty simple and straightforward:

1. Extract all books urls from the listing page
2. For each book URL found in the step 1, fetch the page and extract the resultant item

This logic should work without any change for different books sites because
having pages with lists of books and then detail pages for the individual book is
such a common way of structuring sites.

Let's reuse the very same ``BooksSpider`` spider but now to extract books from a different
page: `bookpage.com/reviews <https://bookpage.com/reviews>`_.

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

The last step is configuring ``scrapy-poet`` so that these Page Objects
are used for Book Page URLs. This can be done by configuring
``SCRAPY_POET_OVERRIDES`` in the Scrapy ``settings.py`` configuration file.

.. code-block:: python

    SCRAPY_POET_OVERRIDES = {
        "bookpage.com": {
            BookListPage: BPBookListPage,
            BookPage: BPBookPage
        }
    }

``SCRAPY_POET_OVERRIDES`` contain rules that overrides the Page Objects
used for a particular domain. In this particular case, Page Objects
``BPBookListPage`` and ``BPBookPage`` will be used instead of
``BookListPage`` and ``BPBookPage`` for any request whose domain is
``bookpage.com``.

The spider is now ready to extract books from both sites 😀.
The full example
`can be seen here <https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders/books_04_overrides_01.py>`_

Page Objects refinement
=======================

Any ``Injectable`` or page input can be overridden. But the overriding
mechanism stops for the children of any already overridden type. This opens
the door to refining existing Page Objects without getting trapped in a cyclic
dependency. For example, you might have an existing Page Object for book extraction:

.. code-block:: python

    class BookPage(ItemWebPage):
        def to_item(self):
            ...

Imagine this Page Object is provided by an external library, so you cannot
directly modify it. But you want to extract an additional attribute (e.g. ``ISBN``) that
was not extracted by the original Page Object. No problem, you can just override it
using the following Page Object:

.. code-block:: python

    class ISBNBookPage(ItemWebPage):

        def __init__(self, book_page: BookPage):
            self.book_page = book_page

        def to_item(self):
            item = self.book_page.to_item()
            item['isbn'] = self.css(".isbn-class::text").get()
            return item

And then override it for a particular domain using ``settings.py``:

.. code-block:: python

    SCRAPY_POET_OVERRIDES = {
        "example.com": {
            BookPage: ISBNBookPage
        }
    }

This new Page Objects gets the original ``BookPage`` as dependency and enrich
the obtained item with the ISBN.

.. note::

    By design overrides rules are not applied to ``ISBNBookPage`` dependencies
    as it is an overridden type. If they were,
    it would end up in a cyclic dependency error because ``ISBNBookPage`` would
    depend on itself!

Overrides registry
==================

The overrides registry is responsible for informing whether there exists an
override for a particular type for a given response. The default overrides
registry keeps a map of overrides for each domain and read this configuration
from settings ``SCRAPY_POET_OVERRIDES`` as has been seen in the sections above.

But the registry implementation can be changed at convenience. A different
registry implementation can be configured using the property
``SCRAPY_POET_OVERRIDES_REGISTRY`` in ``settings.py``. The new registry
must be a subclass of ``scrapy_poet.overrides.OverridesRegistryBase``
that implements the method ``overrides_for``. As other Scrapy components,
it can be initialized from the ``from_crawler`` class method if implemented.
This might be handy to be able to access settings, stats, etc.

