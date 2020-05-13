"""
Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy. callback_for is used to reduce
boilerplate.
"""
import scrapy
from web_poet.pages import ItemWebPage
from scrapy_poet import callback_for


class BookPage(ItemWebPage):
    def to_item(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_02_1'
    start_urls = ['http://books.toscrape.com/']
    parse_book = callback_for(BookPage)

    def parse(self, response):
        for url in response.css('.image_container a::attr(href)').getall():
            yield response.follow(url, self.parse_book)
