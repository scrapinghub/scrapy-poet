# -*- coding: utf-8 -*-
"""
Scrapy spider which uses AutoExtract API, to extract books as products.
"""
import scrapy
from scrapy_po import callback_for

from example.autoextract import ProductPage


class BooksSpider(scrapy.Spider):
    name = 'books_03'
    start_urls = ['http://books.toscrape.com/']
    parse_book = callback_for(ProductPage)

    def parse(self, response):
        for url in response.css('.image_container a::attr(href)').getall():
            yield response.follow(url, self.parse_book)
