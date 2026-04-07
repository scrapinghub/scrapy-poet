"""
Scrapy spider which uses Page Objects both for crawling and extraction.
"""

import scrapy
from web_poet import WebPage

from scrapy_poet import callback_for


class BookListPage(WebPage):
    def book_urls(self):
        return self.css(".image_container a::attr(href)").getall()


class BookPage(WebPage):
    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_03"

    async def start(self) -> None:
        yield scrapy.Request("http://books.toscrape.com/", callback=self.parse)

    def parse(self, response, page: BookListPage) -> None:
        for url in page.book_urls():
            yield response.follow(url, callback_for(BookPage))
