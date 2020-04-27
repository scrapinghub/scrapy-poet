===========
scrapy-poet
===========

.. image:: https://img.shields.io/pypi/v/scrapy-poet.svg
   :target: https://pypi.python.org/pypi/scrapy-poet
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/scrapy-poet.svg
   :target: https://pypi.python.org/pypi/scrapy-poet
   :alt: Supported Python Versions

.. image:: https://travis-ci.com/scrapinghub/scrapy-po.svg?branch=master
   :target: https://travis-ci.com/scrapinghub/scrapy-po
   :alt: Build Status

.. image:: https://codecov.io/github/scrapinghub/scrapy-poet/coverage.svg?branch=master
   :target: https://codecov.io/gh/scrapinghub/scrapy-poet
   :alt: Coverage report

.. warning::
    Current status is "experimental".

``scrapy-poet`` implements Page Object pattern for Scrapy.

License is BSD 3-clause.

Installation
============

::

    pip install scrapy-poet

scrapy-poet requires Python >= 3.6 and Scrapy 2.1.0+.

Usage
=====

First, enable middleware in your settings.py::

    DOWNLOADER_MIDDLEWARES = {
       'scrapy_poet.InjectionMiddleware': 543,
    }

After that you can write spiders which use page object pattern to separate
extraction code from a spider:

.. code-block:: python

    import scrapy
    from web_poet.pages import WebPage


    class BookPage(WebPage):
        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }


    class BooksSpider(scrapy.Spider):
        name = 'books'
        start_urls = ['http://books.toscrape.com/']

        def parse(self, response):
            for url in response.css('.image_container a::attr(href)').getall():
                yield response.follow(url, self.parse_book)

        def parse_book(self, response, book_page: BookPage):
            yield book_page.to_item()

TODO: document motivation, the rest of the features, provide
more usage examples, explain shortcuts, etc.
For now, please check spiders in "example" folder:
https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

Contributing
============

* Source code: https://github.com/scrapinghub/scrapy-poet
* Issue tracker: https://github.com/scrapinghub/scrapy-poet/issues

Use tox_ to run tests with different Python versions::

    tox

The command above also runs type checks; we use mypy.

.. _tox: https://tox.readthedocs.io
