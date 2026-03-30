"""
Scrapy spider with reusable components used for two types of pages:
* Listings page, with the components: book list and pagination
* Detail book page, with the components: the item itself, the breadcrumbs and
  the recently viewed list of books

All links to detail book pages are found are followed.
All links to search result pages are followed as well.

Scrapy > 2.0 required
"""

import attr
import scrapy
from web_poet import Injectable, WebPage


class ListingsExtractor(WebPage):
    def urls(self):
        return self.css(".image_container a::attr(href)").getall()


class PaginationExtractor(WebPage):
    def urls(self):
        return self.css(".pager a::attr(href)").getall()


class BreadcrumbsExtractor(WebPage):
    def urls(self):
        return self.css(".breadcrumb a::attr(href)").getall()


@attr.s(auto_attribs=True)
class ListingsPage(Injectable):
    book_list: ListingsExtractor
    pagination: PaginationExtractor


@attr.s(auto_attribs=True)
class BookPage(WebPage):
    breadcrumbs: BreadcrumbsExtractor

    def recently_viewed_urls(self):
        return self.css(".image_container a::attr(href)").getall()

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_06"

    async def start(self):
        yield scrapy.Request("http://books.toscrape.com/", callback=self.parse)

    def parse(self, response, page: ListingsPage):
        """Callback for Listings pages"""
        yield from response.follow_all(page.book_list.urls(), self.parse_book)
        yield from response.follow_all(page.pagination.urls(), self.parse, priority=+10)

    def parse_book(self, response, page: BookPage):
        yield from response.follow_all(page.recently_viewed_urls(), self.parse_book)
        yield from response.follow_all(page.breadcrumbs.urls(), self.parse)
        yield page.to_item()
