# -*- coding: utf-8 -*-
import inspect
from typing import Tuple, Dict, Type, Callable, Optional

import andi
from scrapy.http import Request, Response
from scrapy.utils.defer import maybeDeferred_coro
from twisted.internet.defer import inlineCallbacks, returnValue

from web_poet.pages import ItemPage, is_injectable
from scrapy_poet.page_input_providers import providers, PageObjectInputProvider


_CALLBACK_FOR_MARKER = '__scrapy_poet_callback'


def get_callback(request, spider):
    """Get request.callback of a scrapy.Request, as a callable."""
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback


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

    If your ``PageObjectInputProvider`` doesn't need a request, you simply
    don't need to list it as a dependency. But if you need, for example, the
    original request's URL, you can use ``DummyResponse`` instead of
    ``Response``:

    .. code-block:: python

        @provides(ResponseData)
        class ResponseDataProvider(PageObjectInputProvider):

            def __init__(self, response: DummyResponse):
                self.response = response

            def __call__(self):
                return ResponseData(
                    url=self.response.url,
                    html=self.get_data()
                )

            def get_data(self):
                # make an api call
                # make a database query
                # read from disk
                # ...
                pass
    """

    def __init__(self, url: str, request=Optional[Request]):
        super(DummyResponse, self).__init__(url=url, request=request)


def is_callback_using_response(callback: Callable):
    """Check whether the request's callback method is going to use response."""
    if getattr(callback, _CALLBACK_FOR_MARKER, False) is True:
        # The callback_for function was used to create this callback.
        return False

    signature = inspect.signature(callback)
    first_parameter_key = next(iter(signature.parameters))
    first_parameter = signature.parameters[first_parameter_key]
    if str(first_parameter).startswith('*'):
        # Parse method is probably using *args and **kwargs annotation.
        # Let's assume response is going to be used.
        return True

    if first_parameter.annotation is first_parameter.empty:
        # There's no type annotation, so we're probably using response here.
        return True

    if issubclass(first_parameter.annotation, DummyResponse):
        # Type annotation is DummyResponse, so we're probably NOT using it.
        return False

    # Type annotation is not DummyResponse, so we're probably using it.
    return True


def is_provider_using_response(provider):
    """Check whether injectable provider makes use of a valid Response."""
    for argument, possible_types in andi.inspect(provider.__init__).items():
        for cls in possible_types:
            if not issubclass(cls, Response):
                # Type annotation is not a sub-class of Response.
                continue

            if issubclass(cls, DummyResponse):
                # Type annotation is a DummyResponse.
                continue

            # Type annotation is a sub-class of Response, but not a sub-class
            # of DummyResponse, so we're probably using it.
            return True

    # Could not find any Response type annotation in the used providers.
    return False


def is_response_going_to_be_used(request, spider):
    """Check whether the request's response is going to be used."""
    callback = get_callback(request, spider)
    if is_callback_using_response(callback):
        return True

    plan, _ = build_plan(callback, None)
    for provider in get_providers(plan):
        if is_provider_using_response(provider):
            return True

    return False


def get_providers(plan: andi.Plan):
    for obj, _ in plan:
        provider = providers.get(obj)  # type: ignore
        if not provider:
            continue

        yield provider


def build_plan(callback, response
               ) -> Tuple[andi.Plan, Dict[Type, PageObjectInputProvider]]:
    """Build a plan for the injection in the callback."""
    provider_instances = build_providers(response)
    plan = andi.plan(
        callback,
        is_injectable=is_injectable,
        externally_provided=provider_instances.keys()
    )
    return plan, provider_instances


def build_providers(response) -> Dict[Type, PageObjectInputProvider]:
    # find out what resources are available
    result = {}
    for cls, provider in providers.items():
        if andi.inspect(provider.__init__):
            result[cls] = provider(response)  # type: ignore
        else:
            result[cls] = provider()

    return result


@inlineCallbacks
def build_instances(plan: andi.Plan, providers):
    """Build the instances dict from a plan."""
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in providers:
            instances[cls] = yield maybeDeferred_coro(providers[cls])
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    raise returnValue(instances)


def callback_for(page_cls: Type[ItemPage]) -> Callable:
    """This function is a helper for creating callbacks for ``ItemPage``
    sub-classes. The generated callback should return the result of the
    call to the ``ItemPage.to_item`` method.

    The generated callback could be used as a spider instance method or passed
    as an inline/anonymous argument. Make sure to define it as a spider
    argument if you're planning to use disk queues because in this case,
    Scrapy should be able to serialize your request object.

    Example:

    .. code-block:: python

        class BooksSpider(scrapy.Spider):

            name = 'books'
            start_urls = ['http://books.toscrape.com/']

            def parse(self, response):
                query = '.image_container a::attr(href)'
                for url in response.css(query).getall():
                    yield response.follow(url, self.parse_book)

            def parse_book(self, response, book_page: BookPage):
                yield book_page.to_item()
    """
    if not issubclass(page_cls, ItemPage):
        raise TypeError(
            f'{page_cls.__name__} should be a sub-class of ItemPage.')

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
