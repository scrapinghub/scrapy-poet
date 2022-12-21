"""
This example doesn't work!

Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy.

Page object is used instead of callback below. It doesn't work now,
but it can be implemented, with Scrapy support.
"""
import scrapy
from web_poet import WebPage


class BookPage(WebPage):
    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_02_3"

    def start_requests(self):
        yield scrapy.Request("http://books.toscrape.com/", self.parse_home)

    def parse_home(self, response):
        for url in response.css(".image_container a::attr(href)").getall():
            yield response.follow(url, BookPage)
