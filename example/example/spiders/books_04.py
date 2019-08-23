# -*- coding: utf-8 -*-
"""
Scrapy spider which uses Page Objects both for crawling and extraction.
"""
import scrapy

from scrapy_po import WebPage


class BookListPage(WebPage):
    def product_urls(self):
        return self.css('.image_container a::attr(href)').getall()


class BookPage(WebPage):
    def to_item(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_04'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page: BookListPage):
        for url in page.product_urls():
            yield response.follow(url, self.parse_book)

    def parse_book(self, response, page: BookPage):
        yield page.to_item()
