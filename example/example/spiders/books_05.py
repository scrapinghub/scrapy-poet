"""
Scrapy spider which uses Page Objects both for crawling and extraction.
You can mix various page types freely.
"""
import scrapy

from core_po.objects import WebPageObject

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
    name = 'books_05'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page_object: BookListPageObject):
        for url in page_object.serialize():
            yield response.follow(url, self.parse_book)

    def parse_book(self, response, page_object: BookPageObject):
        # you can also post-process data in a spider
        book = page_object.serialize()
        book['title'] = book.pop('name')
        yield book
