"""
Scrapy spider which uses AutoExtract API, to extract books as products.
"""
import scrapy
from example.autoextract import ProductPage

from scrapy_poet import callback_for


class BooksSpider(scrapy.Spider):
    name = "books_03"

    def start_requests(self):
        yield scrapy.Request("http://books.toscrape.com/", self.parse_home)

    def parse_home(self, response):
        for url in response.css(".image_container a::attr(href)").getall():
            yield response.follow(url, callback_for(ProductPage))
