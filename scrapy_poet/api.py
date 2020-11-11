from typing import Callable, Optional, Type

from scrapy.http import Request, Response

from web_poet.pages import ItemPage


_CALLBACK_FOR_MARKER = '__scrapy_poet_callback'


class DummyResponse(Response):
    """This class is returned by the ``InjectionMiddleware`` when it detects
    that the download could be skipped. It inherits from Scrapy ``Response``
    and signals and stores the URL and references the original ``Request``.

    If you want to skip downloads, you can type annotate your parse method
    with this class.

    .. code-block:: python

        def parse(self, response: DummyResponse):
            pass

    If there's no Page Input that depends on a Scrapy ``Response``, the
    ``InjectionMiddleware`` is going to skip download and provide a
    ``DummyResponse`` to your parser instead.
    """

    def __init__(self, url: str, request=Optional[Request]):
        super().__init__(url=url, request=request)


def callback_for(page_cls: Type[ItemPage]) -> Callable:
    """Create a callback for an :class:`web_poet.pages.ItemPage` subclass.

    The generated callback returns the output of the
    ``ItemPage.to_item()`` method, i.e. extracts a single item
    from a web page, using a Page Object.

    This helper allows to reduce the boilerplate when working
    with Page Objects. For example, instead of this:

    .. code-block:: python

        class BooksSpider(scrapy.Spider):
            name = 'books'
            start_urls = ['http://books.toscrape.com/']

            def parse(self, response):
                links = response.css('.image_container a')
                yield from response.follow_all(links, self.parse_book)

            def parse_book(self, response: DummyResponse, page: BookPage):
                return page.to_item()

    It allows to write this:

    .. code-block:: python

        class BooksSpider(scrapy.Spider):
            name = 'books'
            start_urls = ['http://books.toscrape.com/']

            def parse(self, response):
                links = response.css('.image_container a')
                yield from response.follow_all(links, self.parse_book)

            parse_book = callback_for(BookPage)

    The generated callback could be used as a spider instance method or passed
    as an inline/anonymous argument. Make sure to define it as a spider
    attribute (as shown in the example above) if you're planning to use
    disk queues, because in this case Scrapy is able to serialize
    your request object.
    """
    if not issubclass(page_cls, ItemPage):
        raise TypeError(
            f'{page_cls.__name__} should be a subclass of ItemPage.')

    if getattr(page_cls.to_item, '__isabstractmethod__', False):
        raise NotImplementedError(
            f'{page_cls.__name__} should implement to_item method.')

    # When the callback is used as an instance method of the spider, it expects
    # to receive 'self' as its first argument. When used as a simple inline
    # function, it expects to receive a response as its first argument.
    #
    # To avoid a TypeError, we need to receive a list of unnamed arguments and
    # a dict of named arguments after our injectable.
    def parse(*args, page: page_cls, **kwargs):  # type: ignore
        yield page.to_item()  # type: ignore

    setattr(parse, _CALLBACK_FOR_MARKER, True)
    return parse
