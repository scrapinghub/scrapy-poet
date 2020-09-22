"""The Injection Middleware needs a standard way to build dependencies for
the Page Inputs used by the request callbacks. That's why we have created a
repository of ``PageObjectInputProviders``.

You could implement different providers in order to acquire data from multiple
external sources, for example, Splash or Auto Extract API.
"""
import abc
import typing

from scrapy.http import Response
from web_poet.page_inputs import ResponseData


class PageObjectInputProvider(abc.ABC):
    """This is an abstract class for describing Page Object Input Providers."""

    provided_classes: typing.Set[typing.Type]

    def __init__(self):
        """You can override this method to receive external dependencies.

        Currently, scrapy-poet is able to inject instances of the following
        classes as *provider* dependencies:

        - :class:`~scrapy.http.Request`
        - :class:`~scrapy.http.Response`
        - :class:`~scrapy.crawler.Crawler`
        - :class:`~scrapy.settings.Settings`
        - :class:`~scrapy.statscollectors.StatsCollector`

        .. warning::

            Scrapy doesn't know when a Request is going to generate
            a Response, a TextResponse, an HtmlResponse,
            or any other type that inherits from Response.
            Because of this,
            you should always annotate your provider's response argument
            with the Response type.
            If your provider needs a TextResponse,
            you need to validate it by yourself,
            the same way you would need to do when using Scrapy callbacks.
            Example:

            .. code-block:: python

                @provides(MyCustomResponseData)
                class MyCustomResponseDataProvider(PageObjectInputProvider):

                    def __init__(self, response: Response):
                        assert isinstance(response, TextResponse)
                        self.response = response
        """

    @abc.abstractmethod
    def __call__(self, provided_classes: typing.Set[typing.Type]) -> typing.Dict[typing.Type, typing.Any]:
        """This method is responsible for building Page Input dependencies."""


class ResponseDataProvider(PageObjectInputProvider):
    """This class provides ``web_poet.page_inputs.ResponseData`` instances."""

    provided_classes = {ResponseData}

    def __init__(self, response: Response):
        """This class receives a Scrapy ``Response`` as a dependency."""
        self.response = response

    def __call__(self, provided_classes: typing.Set[typing.Type]):
        """Builds a ``ResponseData`` instance using a Scrapy ``Response``."""
        return {
            ResponseData: ResponseData(
                url=self.response.url,
                html=self.response.text
            )
        }
