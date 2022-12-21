"""
Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy. callback_for is used to reduce
boilerplate.
"""
import scrapy
from web_poet import WebPage

from scrapy_poet import callback_for


class BookPage(WebPage):
    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_02_1"
    parse_book = callback_for(BookPage)

    def start_requests(self):
        yield scrapy.Request("http://books.toscrape.com/", self.parse_home)

    def parse_home(self, response):
        for url in response.css(".image_container a::attr(href)").getall():
            yield response.follow(url, self.parse_book)
