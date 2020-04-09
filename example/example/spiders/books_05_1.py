# -*- coding: utf-8 -*-
"""
Scrapy spider which uses Page Objects both for crawling and extraction.
You can mix various page types freely.
"""
from typing import Optional

import scrapy

from scrapy_po import WebPage
from scrapy_po.utils import DummyResponse
from example.autoextract import ProductPage


class BookListPage(WebPage):
    def product_urls(self):
        return self.css('.image_container a::attr(href)').getall()


class BookPage(ProductPage):
    def to_item(self):
        # post-processing example: return only 2 fields
        book = super().to_item()
        return {
            'url': book['url'],
            'name': book['name'],
        }


class BooksSpider(scrapy.Spider):
    name = 'books_05_1'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page: BookListPage):
        for url in page.product_urls():
            yield response.follow(url, self.parse_book)

    # Bypassing download using DummyResponse since we'll be using AutoExtract.
    def parse_book(self, response: DummyResponse, page: BookPage):
        # you can also post-process data in a spider
        book = page.to_item()
        book['title'] = book.pop('name')
        yield book
