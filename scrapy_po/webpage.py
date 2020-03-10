# -*- coding: utf-8 -*-
import abc

import attr
import parsel

from .page_inputs import ResponseData


class Injectable(abc.ABC):
    """
    Injectable objects are automatically built and passed as arguments to
    callbacks that requires them. The ``InjectionMiddleware`` take care of it.

    Instead of inheriting you can also use ``Injectable.register(MyWebPage)``.
    ``Injectable.register`` can also be used as a decorator.
    """
    pass


# NoneType is considered as injectable. Required for Optionals to work
Injectable.register(type(None))


class ItemPage(Injectable):
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
class WebPage(Injectable, ResponseShortcutsMixin):
    """
    Default WebPage class. It uses basic response data (html, url),
    and provides xpath / css shortcuts.

    This class is most useful as a base class for page objects, when
    extraction logic is similar to what's usually happening in scrapy
    spider callbacks.
    """
    response: ResponseData


@attr.s(auto_attribs=True)
class ItemWebPage(WebPage, ItemPage):
    """
    ``WebPage`` that implements the ``to_item`` method.
    """
    pass


def callback_for(page_cls):
    """ Helper for defining callbacks for pages with to_item methods """
    def parse(*args, page: page_cls):
        yield page.to_item()  # type: ignore
    return parse

