import abc


class PageObjectInputProvider(abc.ABC):
    """This is an abstract class for describing Page Object Input Providers."""

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
    def __call__(self):
        """This method is responsible for building Page Input dependencies."""
