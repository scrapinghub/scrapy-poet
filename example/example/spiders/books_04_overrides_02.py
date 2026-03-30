"""
Scrapy spider which uses Page Objects both for crawling and extraction,
and uses overrides to support two different sites without changing
the crawling logic (the spider is exactly the same)

No configured default logic: if used for an unregistered domain, no logic
at all is applied.
"""

import scrapy
from web_poet import WebPage
from web_poet.rules import ApplyRule

from scrapy_poet import callback_for


class BookListPage(WebPage):
    def book_urls(self):
        return []


class BookPage(WebPage):
    pass


class BTSBookListPage(BookListPage):
    """Logic to extract listings from pages like https://books.toscrape.com"""

    def book_urls(self):
        return self.css(".image_container a::attr(href)").getall()


class BTSBookPage(BookPage):
    """Logic to extract book info from pages like https://books.toscrape.com/catalogue/soumission_998/index.html"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BPBookListPage(BookListPage):
    """Logic to extract listings from pages like https://bookpage.com/reviews"""

    def book_urls(self):
        return self.css("article.post h4 a::attr(href)").getall()


class BPBookPage(BookPage):
    """Logic to extract from pages like https://bookpage.com/reviews/25879-laird-hunt-zorrie-fiction"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("body div > h1::text").get().strip(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_04_overrides_02"
    # Configuring different page objects pages for different domains
    custom_settings = {
        "SCRAPY_POET_RULES": [
            ApplyRule("toscrape.com", use=BTSBookListPage, instead_of=BookListPage),
            ApplyRule("toscrape.com", use=BTSBookPage, instead_of=BookPage),
            ApplyRule("bookpage.com", use=BPBookListPage, instead_of=BookListPage),
            ApplyRule("bookpage.com", use=BPBookPage, instead_of=BookPage),
        ]
    }

    async def start(self):
        for url in ["http://books.toscrape.com/", "https://bookpage.com/reviews"]:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response, page: BookListPage):
        yield from response.follow_all(page.book_urls(), callback_for(BookPage))
