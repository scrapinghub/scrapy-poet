===============
Getting started
===============

The goal of this project is to make reusable Page Objects that separates
extraction logic from crawling. They could be easily tested and distributed
across different projects. Also, they could make use of different backends,
for example, acquiring data from Splash and Auto Extract API.

This project easily integrates Page Objects created using `web-poet`_ with
Scrapy through the configuration of a dependency injection middleware.

License is BSD 3-clause.



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

.. _`web-poet`: https://github.com/scrapinghub/web-poet
