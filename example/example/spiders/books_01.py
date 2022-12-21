"""
Baseline: regular Scrapy spider, sweet & easy.
"""
import scrapy


class BooksSpider(scrapy.Spider):
    name = "books_01"

    def start_requests(self):
        yield scrapy.Request("http://books.toscrape.com/", self.parse_home)

    def parse_home(self, response):
        for url in response.css(".image_container a::attr(href)").getall():
            yield response.follow(url, self.parse_book)

    def parse_book(self, response):
        yield {
            "url": response.url,
            "name": response.css("title::text").get(),
        }
