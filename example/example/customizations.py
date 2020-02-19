from typing import Type

from urllib.request import Request

from example.spiders.books_06 import AsimovFoundationBookPage, BookPage
from scrapy_po.customizations import Customizations


class ExampleCustomizations(Customizations):

    def __call__(self, request: Request, response, spider, cls: Type) -> Type:
        if response.url == "http://books.toscrape.com/catalogue/foundation-foundation-publication-order-1_375/index.html":
            if cls == BookPage:
                return AsimovFoundationBookPage
        return cls