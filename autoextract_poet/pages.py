from dataclasses import dataclass

from web_poet.pages import ItemPage

from autoextract_poet.inputs import (
    ProductResponseData,
    ProductListResponseData,
)


@dataclass
class ProductPage(ItemPage):
    """Generic product page."""

    autoextract_response: ProductResponseData

    def to_item(self):
        product = self.autoextract_response.data.get("product", {})
        return product


@dataclass
class ProductListPage(ItemPage):
    """Generic product list page."""

    autoextract_response: ProductListResponseData

    @property
    def _product_list(self):
        return self.autoextract_response.data.get("productList", {})

    def breadcrumbs(self):
        return self._product_list.get("breadcrumbs", [])

    def urls(self):
        urls = [item.get("url") for item in self.to_items()]
        urls = [url for url in urls if url]
        return urls

    def to_items(self):
        return self._product_list.get("products", [])
