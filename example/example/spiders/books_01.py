# -*- coding: utf-8 -*-
"""
Baseline: regular Scrapy spider, sweet & easy.
"""
import scrapy


class BooksSpider(scrapy.Spider):
    name = 'books_01'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response):
        for url in response.css('.image_container a::attr(href)').getall():
            yield response.follow(url, self.parse_book)

    def parse_book(self, response):
        yield {
            'url': response.url,
            'name': response.css("title::text").get(),
        }
