"""
Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy. callback_for is used to reduce
boilerplate.
"""
import scrapy

from core_po.objects import WebPageObject
from scrapy_po import callback_for


class BookPageObject(WebPageObject):

    def serialize(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_02_1'
    start_urls = ['http://books.toscrape.com/']
    parse_book = callback_for(BookPageObject)

    def parse(self, response):
        for url in response.css('.image_container a::attr(href)').getall():
            yield response.follow(url, self.parse_book)
