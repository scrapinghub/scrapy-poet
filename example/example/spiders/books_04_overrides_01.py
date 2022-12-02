"""
Scrapy spider which uses Page Objects both for crawling and extraction,
and uses overrides to support two different sites without changing
the crawling logic (the spider is exactly the same).

The default configured PO logic contains the logic for books.toscrape.com
"""
import scrapy
from web_poet import ApplyRule, WebPage

from scrapy_poet import callback_for


class BookListPage(WebPage):
    """Logic to extract listings from pages like https://books.toscrape.com"""

    def book_urls(self):
        return self.css(".image_container a::attr(href)").getall()


class BookPage(WebPage):
    """Logic to extract book info from pages like https://books.toscrape.com/catalogue/soumission_998/index.html"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("title::text").get(),
        }


class BPBookListPage(WebPage):
    """Logic to extract listings from pages like https://bookpage.com/reviews"""

    def book_urls(self):
        return self.css("article.post h4 a::attr(href)").getall()


class BPBookPage(WebPage):
    """Logic to extract from pages like https://bookpage.com/reviews/25879-laird-hunt-zorrie-fiction"""

    def to_item(self):
        return {
            "url": self.url,
            "name": self.css("body div > h1::text").get().strip(),
        }


class BooksSpider(scrapy.Spider):
    name = "books_04_overrides_01"
    start_urls = ["http://books.toscrape.com/", "https://bookpage.com/reviews"]
    # Configuring different page objects pages from the bookpage.com domain
    custom_settings = {
        "SCRAPY_POET_OVERRIDES": [
            ApplyRule("bookpage.com", use=BPBookListPage, instead_of=BookListPage),
            ApplyRule("bookpage.com", use=BPBookPage, instead_of=BookPage),
        ]
    }

    def parse(self, response, page: BookListPage):
        for url in page.book_urls():
            yield response.follow(url, callback_for(BookPage))
