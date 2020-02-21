# -*- coding: utf-8 -*-
import abc

import attr
import parsel

from .page_inputs import ResponseData


class PageObject(abc.ABC):
    """
    All web page objects should inherit from this class.
    It is a marker for a middleware to pick anargument and populate it.

    Instead of inheriting you can also use ``PageObject.register(MyWebPage)``.
    """
    pass


class ItemPage(PageObject):
    """ Page Object which requires to_item method to be implemented. """
    @abc.abstractmethod
    def to_item(self):
        pass


class ResponseShortcutsMixin:
    """
    A mixin with common shortcut methods for working with self.response.
    It requires "response" attribute to be present.
    """
    _cached_selector = None

    @property
    def selector(self) -> parsel.Selector:
        from parsel.selector import Selector
        if self._cached_selector is None:
            self._cached_selector = Selector(self.html)
        return self._cached_selector

    @property
    def url(self):
        return self.response.url

    @property
    def html(self):
        return self.response.html

    def xpath(self, query, **kwargs):
        return self.selector.xpath(query, **kwargs)

    def css(self, query):
        return self.selector.css(query)


@attr.s(auto_attribs=True)
class WebPage(PageObject, ResponseShortcutsMixin):
    """
    Default WebPage class. It uses basic response data (html, url),
    and provides xpath / css shortcuts.

    This class is most useful as a base class for page objects, when
    extraction logic is similar to what's usually happening in scrapy
    spider callbacks.
    """
    response: ResponseData


@attr.s(auto_attribs=True)
class PageComponent(PageObject, ResponseShortcutsMixin):
    """
    Use it for implementing extractors for particular components of the
    page (i.e. breadcrumbs) that can be reused across different page objects.

    For example, a book page object can rely on breadcrumbs page component
    to extract the book category and also a book listings page object could
    rely in this component to extract the category a listings page
    belongs to.
    """
    response: ResponseData


def callback_for(page_cls):
    """ Helper for defining callbacks for pages with to_item methods """
    def parse(*args, page: page_cls):
        return page.to_item()  # type: ignore
    return parse

