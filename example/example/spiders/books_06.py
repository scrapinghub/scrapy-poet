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

from scrapy_po import WebPage, ItemWebPage, Injectable


class ListingsExtractor(WebPage):
    def urls(self):
        return self.css('.image_container a::attr(href)').getall()


class PaginationExtractor(WebPage):
    def urls(self):
        return self.css('.pager a::attr(href)').getall()


class BreadcrumbsExtractor(WebPage):
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
    name = 'books_06'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page: ListingsPage):
        """ Callback for Listings pages """
        yield from self.follow_listing(response, page.book_list)
        yield from self.follow_pagination(response, page.pagination)

    def parse_book(self, response, page: BookPage):
        yield from self.follow_listing(response, page.recently_viewed)
        yield from self.follow_breadcrumbs(response, page.breadcrumbs)
        yield page.to_item()

    def follow_listing(self, response, item_list: ListingsExtractor):
        for url in item_list.urls():
            yield response.follow(url, self.parse_book)

    def follow_pagination(self, response, pagination: PaginationExtractor):
        for url in pagination.urls():
            yield response.follow(url, self.parse, priority=+10)

    def follow_breadcrumbs(self, response, breadcrumbs: BreadcrumbsExtractor):
        for url in breadcrumbs.urls():
            yield response.follow(url, self.parse)
