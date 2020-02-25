# -*- coding: utf-8 -*-
"""
Scrapy spider with reusable components used for two types of pages:
* Listings page, with the components: book list and pagination
* Detail book page, with the components: the item itself, the breadcrumbs and
  the recently viewed list of books

All links to detail book pages are found are followed.
All links to search result pages are followed as well.
"""

import scrapy
import attr

from scrapy_po import WebPage, ItemWebPage, Injectable, RequestsFromUrlsMixin


class ListingsExtractor(WebPage, RequestsFromUrlsMixin):
    def urls(self):
        return self.css('.image_container a::attr(href)').getall()


class PaginationExtractor(WebPage, RequestsFromUrlsMixin):
    def urls(self):
        return self.css('.pager a::attr(href)').getall()


class BreadcrumbsExtractor(WebPage, RequestsFromUrlsMixin):
    def urls(self):
        return self.css('.breadcrumb a::attr(href)').getall()


@attr.s(auto_attribs=True)
class ListingsPage(Injectable):
    book_list: ListingsExtractor
    pagination: PaginationExtractor


@attr.s(auto_attribs=True)
class BookPage(ItemWebPage):
    recently_viewed: ListingsExtractor
    breadcrumbs: BreadcrumbsExtractor

    def to_item(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_06_2'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page: ListingsPage):
        """ Callback for Listings pages """
        yield from page.book_list.requests(self.parse_book)
        yield from page.pagination.requests(self.parse, priority=+10)

    def parse_book(self, response, page: BookPage):
        yield from page.recently_viewed.requests(self.parse_book)
        yield from page.breadcrumbs.requests(self.parse)
        yield page.to_item()
