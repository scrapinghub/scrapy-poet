"""
Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy.

callback_for is used to reduce boilerplate, right in a parse method.
This makes code more readable, but has a problem - callback is created
on fly, so it doesn't work with disk queues.

It should be possible to fix this limitation, so even though this code
has problems now, it is used in the latter examples, because as an API
it is better than defining callback explicitly.
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
    name = "books_02_2"

    def start_requests(self):
        yield scrapy.Request("http://books.toscrape.com/", self.parse_home)

    def parse_home(self, response):
        for url in response.css(".image_container a::attr(href)").getall():
            yield response.follow(url, callback_for(BookPage))
