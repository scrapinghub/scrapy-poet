"""
Scrapy spider which uses Page Objects both for crawling and extraction,
and uses overrides to support two different sites without changing
the crawling logic (the spider is exactly the same)

No configured default logic: if used for an unregistered domain, no logic
at all is applied.
"""
import scrapy
from web_poet import ItemWebPage, WebPage
from scrapy_poet import callback_for


class BookListPage(WebPage):

    def product_urls(self):
        return []


class BookPage(ItemWebPage):

    def to_item(self):
        return {}


class BTSBookListPage(BookListPage):
    """Logic to extract listings from pages like https://books.toscrape.com"""
    def product_urls(self):
        return self.css('.image_container a::attr(href)').getall()


class BTSBookPage(BookPage):
    """Logic to extract book info from pages like https://books.toscrape.com/catalogue/soumission_998/index.html"""
    def to_item(self):
        return {
            'url': self.url,
            'name': self.css("title::text").get(),
        }


class BPBookListPage(BookListPage):
    """Logic to extract listings from pages like https://bookpage.com/reviews"""
    def product_urls(self):
        return self.css('.article-info a::attr(href)').getall()


class BPBookPage(BookPage):
    """Logic to extract from pages like https://bookpage.com/reviews/25879-laird-hunt-zorrie-fiction"""
    def to_item(self):
        return {
            'url': self.url,
            'name': self.css(".book-data h4::text").get().strip(),
        }


class BooksSpider(scrapy.Spider):
    name = 'books_04_overrides_02'
    start_urls = ['http://books.toscrape.com/', 'https://bookpage.com/reviews']
    # Configuring different page objects pages for different domains
    custom_settings = {
        "SCRAPY_POET_OVERRIDES": {
            "toscrape.com": {
                BookListPage: BTSBookListPage,
                BookPage: BTSBookPage
            },
            "bookpage.com": {
                BookListPage: BPBookListPage,
                BookPage: BPBookPage
            },
        }
    }

    def parse(self, response, page: BookListPage):
        for url in page.product_urls():
            yield response.follow(url, callback_for(BookPage))
