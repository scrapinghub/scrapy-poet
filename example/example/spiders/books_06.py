"""
Scrapy spider with reusable components used for two types of pages:
* Listings page, with the components: book list and pagination
* Detail book page, with the components: the item itself, the breadcrumbs and
  the recently viewed list of books

All links to detail book pages are found are followed.
All links to search result pages are followed as well.

Scrapy > 2.0 required
"""

import scrapy
import attr

from core_po.objects import Injectable, WebPageObject


class ListingsExtractor(WebPageObject):

    def serialize(self):
        return self.css('.image_container a::attr(href)').getall()


class PaginationExtractor(WebPageObject):

    def serialize(self):
        return self.css('.pager a::attr(href)').getall()


class BreadcrumbsExtractor(WebPageObject):

    def serialize(self):
        return self.css('.breadcrumb a::attr(href)').getall()


@attr.s(auto_attribs=True)
class ListingsPage(Injectable):

    book_list: ListingsExtractor
    pagination: PaginationExtractor


@attr.s(auto_attribs=True)
class BookPage(WebPageObject):

    breadcrumbs: BreadcrumbsExtractor

    def recently_viewed_urls(self):
        return self.css('.image_container a::attr(href)').getall()

    def serialize(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):

    name = 'books_06'
    start_urls = ['http://books.toscrape.com/']

    def parse(self, response, page_object: ListingsPage):
        """ Callback for Listings pages """
        yield from response.follow_all(page_object.book_list.serialize(), self.parse_book)
        yield from response.follow_all(page_object.pagination.serialize(), self.parse, priority=+10)

    def parse_book(self, response, page_object: BookPage):
        yield from response.follow_all(page_object.recently_viewed_urls(), self.parse_book)
        yield from response.follow_all(page_object.breadcrumbs.serialize(), self.parse)
        yield page_object.serialize()
