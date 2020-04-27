# -*- coding: utf-8 -*-
"""
Scrapy spider which uses Page Objects both for crawling and extraction.
"""
import scrapy
from web_poet.pages import WebPage
from scrapy_poet import callback_for


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
            yield response.follow(url, callback_for(BookPage))
