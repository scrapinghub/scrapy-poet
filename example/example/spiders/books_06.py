# -*- coding: utf-8 -*-
"""
Scrapy spider which uses a PageCollection to store Page Objects both for crawling and extraction.
"""
from typing import List
import scrapy

from scrapy_po import WebPage


class BookPage(WebPage):
    def to_item(self):
        return {"url": self.url, "name": self.css("title::text").get()}


class PageCollection:
    def __init__(self, expected_items: int, *args, **kwargs) -> None:
        self.pages: List[BookPage] = []
        self.expected_items: int = expected_items

    def add_page(self, page: BookPage) -> None:
        self.pages.append(page)

    def to_item(self) -> dict:
        return {"products": [page.to_item() for page in self.pages]}

    def is_complete(self) -> bool:
        return len(self.pages) == self.expected_items


class BookListPage(WebPage):
    def product_urls(self):
        return self.css(".image_container a::attr(href)").getall()


class BooksSpider(scrapy.Spider):
    name = "books_06"
    start_urls = ["http://books.toscrape.com/"]

    def parse(self, response, page: BookListPage):
        product_urls = page.product_urls()
        page_collection = PageCollection(len(product_urls))
        for url in product_urls:
            yield response.follow(
                url, self.parse_book, cb_kwargs={"page_collection": page_collection}
            )

    def parse_book(self, response, page: BookPage, page_collection: PageCollection):
        page_collection.add_page(page)
        if page_collection.is_complete():
            yield page_collection.to_item()
