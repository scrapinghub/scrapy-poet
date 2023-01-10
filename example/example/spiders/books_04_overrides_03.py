"""
Scrapy spider which uses Page Objects both for crawling and extraction,
and uses overrides to support two different sites without changing
the crawling logic (the spider is exactly the same)

No configured default logic: if used for an unregistered domain, no logic
at all is applied.

This example is quite similar to books_04_overrides_02.py where the only
difference is that this example is using the ``@handle_urls`` decorator to
store the rules in web-poet's registry.
"""
import scrapy
from web_poet import WebPage, default_registry, handle_urls

from scrapy_poet import callback_for


class BookListPage(WebPage):
    def book_urls(self):
        return []


class BookPage(WebPage):
    pass


@handle_urls("toscrape.com", instead_of=BookListPage)
class BTSBookListPage(BookListPage):
    """Logic to extract listings from pages like https://books.toscrape.com"""

    def book_urls(self):
        return self.css(".image_container a::attr(href)").getall()


@handle_urls("toscrape.com", instead_of=BookPage)
class BTSBookPage(BookPage):
    """Logic to extract book info from pages like https://books.toscrape.com/catalogue/soumission_998/index.html"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


@handle_urls("bookpage.com", instead_of=BookListPage)
class BPBookListPage(BookListPage):
    """Logic to extract listings from pages like https://bookpage.com/reviews"""

    def book_urls(self):
        return self.css("article.post h4 a::attr(href)").getall()


@handle_urls("bookpage.com", instead_of=BookPage)
class BPBookPage(BookPage):
    """Logic to extract from pages like https://bookpage.com/reviews/25879-laird-hunt-zorrie-fiction"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("body div > h1::text").get().strip(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_04_overrides_03"
    start_urls = ["http://books.toscrape.com/", "https://bookpage.com/reviews"]
    # Configuring different page objects pages for different domains
    custom_settings = {"SCRAPY_POET_RULES": default_registry.get_rules()}

    def parse(self, response, page: BookListPage):
        yield from response.follow_all(page.book_urls(), callback_for(BookPage))
