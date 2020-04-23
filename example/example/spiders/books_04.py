"""
Scrapy spider which uses Page Objects both for crawling and extraction.
"""
import scrapy

from core_po.objects import WebPageObject
from scrapy_po import callback_for


class BookListPageObject(WebPageObject):

    def serialize(self):
        return self.css('.image_container a::attr(href)').getall()


class BookPageObject(WebPageObject):

    def serialize(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_04'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page_object: BookListPageObject):
        for url in page_object.serialize():
            yield response.follow(url, callback_for(BookPageObject))
