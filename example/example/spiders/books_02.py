# -*- coding: utf-8 -*-
"""
Scrapy spider which uses Page Objects to make extraction code more reusable.
BookPage is now independent of Scrapy.
"""
import scrapy
from core_po.pages import WebPage


class BookPage(WebPage):
    def to_item(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_02'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response):
        for url in response.css('.image_container a::attr(href)').getall():
            yield response.follow(url, self.parse_book)

    def parse_book(self, response, book_page: BookPage):
        yield book_page.to_item()
