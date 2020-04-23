"""
Scrapy spider which uses Page Objects both for crawling and extraction.
You can mix various page types freely.

This example shows how to skip request downloads using DummyResponse type
annotations. You should use this type annotation in your callback method
and make sure that all of your providers don't require the use of a regular
Response injection.

Check the ``example.autoextract.AutoextractProductProvider.__init__`` method
and the ``BooksSpider.parse_book`` callback for implementation details.
"""

import scrapy

from core_po.objects import WebPageObject
from scrapy_po.utils import DummyResponse

from example.autoextract import ProductPageObject


class BookListPageObject(WebPageObject):

    def serialize(self):
        return self.css('.image_container a::attr(href)').getall()


class BookPageObject(ProductPageObject):

    def serialize(self):
        # post-processing example: return only 2 fields
        book = super().serialize()
        return {
            'url': book['url'],
            'name': book['name'],
        }


class BooksSpider(scrapy.Spider):
    name = 'books_05_1'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page_object: BookListPageObject):
        for url in page_object.serialize():
            yield response.follow(url, self.parse_book)

    # Bypassing download using DummyResponse since we'll be using AutoExtract.
    def parse_book(self, response: DummyResponse, page_object: BookPageObject):
        # you can also post-process data in a spider
        book = page_object.serialize()
        book['title'] = book.pop('name')
        yield book
