========
Overview
========

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

``scrapy-poet`` is the `web-poet`_ Page Object pattern implementation for Scrapy.

The goal of this project is to make reusable Page Objects that separates
extraction logic from crawling. They could be easily tested and distributed
across different projects. Also, they could make use of different backends,
for example, acquiring data from Splash and Auto Extract API.

This project easily integrates Page Objects created using `web-poet`_ with
Scrapy through the configuration of a dependency injection middleware.

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
            links = response.css('.image_container a')
            yield from response.follow_all(links, self.parse_book)

        def parse_book(self, response, book_page: BookPage):
            yield book_page.to_item()

Please refer to spiders in "example" folder:
https://github.com/scrapinghub/scrapy-poet/tree/master/example/example/spiders

Contributing
============

* Source code: https://github.com/scrapinghub/scrapy-poet
* Issue tracker: https://github.com/scrapinghub/scrapy-poet/issues

Use tox_ to run tests with different Python versions::

    tox

The command above also runs type checks; we use mypy.

.. toctree::
   :hidden:

.. _tox: https://tox.readthedocs.io
.. _`web-poet`: https://github.com/scrapinghub/web-poet
