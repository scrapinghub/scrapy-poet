=========
Changelog
=========

TBR
---

This release enables scrapy-poet to fully support item classes as dependencies
in page objects and spider callbacks. The following is now possible:
 
.. code-block:: python

    import attrs
    import scrapy
    from web_poet import WebPage, handle_urls, field
    from scrapy_poet import DummyResponse

    @attrs.define
    class Image:
        url: str

    @handle_urls("example.com")
    class ProductImagePage(WebPage[Image]):
        @field
        def url(self) -> str:
            return self.css("#product img ::attr(href)").get("")

    @attrs.define
    class Product:
        name: str
        image: Image

    @handle_urls("example.com")
    @attrs.define
    class ProductPage(WebPage[Product]):
        # ✨ NEW: Notice that the page object can ask for items as dependencies.
        # An instance of ``Image`` is injected behind the scenes by calling the
        # ``.to_item()`` method of ``ProductImagePage``.
        image_item: Image

        @field
        def name(self) -> str:
            return self.css("h1.name ::text").get("")

        @field
        def image(self) -> Image:
            return self.image_item

    class MySpider(scrapy.Spider):
        name = "myspider"

        def start_requests(self):
            yield scrapy.Request(
                "https://example.com/products/some-product", self.parse
            )

        # ✨ NEW: Notice that we're directly using the item here and not the
        # page object.
        def parse(self, response: DummyResponse, item: Product):
            return item

In line with this, the following changes were made:

    * Added a new ``scrapy_poet.page_input_providers.ItemProvider`` which makes
      the usage above possible.
    * Multiple changes to the ``scrapy_poet.PageObjectInputProvider`` base class
      which are backward incompatible:

        * It now accepts an instance of ``scrapy_poet.injection.Injector`` in its
          constructor instead of ``scrapy.crawler.Crawler``. Although you can
          still access the ``scrapy.crawler.Crawler`` via the ``Injector.crawler``
          attribute.
        * ``is_provided()`` is now an instance method instead of a class
          method.

    * The ``scrapy_poet.injection.Injector``'s attribute and constructor parameter 
      called ``overrides_registry`` is now simply called ``registry``.
      This is backwards incompatible.
    * An item type is now supported by ``scrapy_poet.callback_for`` alongside
    * An item class is now supported by ``scrapy_poet.callback_for`` alongside
      the usual page objects. This means that it won't raise a ``TypeError``
      anymore when not passing a subclass of ``web_poet.ItemPage``.
    * ``scrapy_poet.overrides.OverridesRegistry`` has been deprecated and
      overhauled into ``scrapy_poet.registry.OverridesAndItemRegistry``:

        * It is now subclassed from ``web_poet.RulesRegistry`` which allows
          outright access to its registry methods.
        * It now allows retrieval of rules based on the returned item class.
        * The registry doesn't accept tuples as rules anymore. Only
          ``web_poet.ApplyRule`` instances are allowed. The same goes for
          ``SCRAPY_POET_RULES`` (and the deprecated ``SCRAPY_POET_OVERRIDES``).

            * As a result, the following type aliases have been removed:
              ``scrapy_poet.overrides.RuleAsTuple`` and
              ``scrapy_poet.overrides.RuleFromUser``
            * These changes are backward incompatible.

    * New exception: ``scrapy_poet.injector_error.ProviderDependencyDeadlockError``.
      This is raised when it's not possible to create the dependencies due to
      a deadlock in their sub-dependencies, e.g. due to a circular dependency
      between page objects.

Other changes:

    * Moved some of the utility functions from the test module into
      ``scrapy_poet.utils.testing``.
    * Documentation improvements.

Deprecations:

    * The ``scrapy_poet.overrides`` module has been replaced by
      ``scrapy_poet.registry``.
    * The ``scrapy_poet.overrides.OverridesRegistry`` class is now replaced by
      ``scrapy_poet.registry.OverridesAndItemRegistry``.
    * The ``SCRAPY_POET_OVERRIDES_REGISTRY`` setting has been replaced by
      ``SCRAPY_POET_REGISTRY``.
    * The ``SCRAPY_POET_OVERRIDES`` setting has been replaced by
      ``SCRAPY_POET_RULES``.
    * Official support for Python 3.11

0.6.0 (2022-11-24)
------------------

* Now requires ``web-poet >= 0.6.0``.

    * All examples in the docs and tests now use ``web_poet.WebPage``
      instead of ``web_poet.ItemWebPage``.
    * The new ``instead_of`` parameter of the ``@handle_urls`` decorator
      is now preferred instead of the deprecated ``overrides`` parameter.
    * ``scrapy_poet.callback_for`` doesn't require an implemented ``to_item``
      method anymore.
    * The new ``web_poet.rules.RulesRegistry`` is used instead of the old
      ``web_poet.overrides.PageObjectRegistry``.
    * The Registry now uses ``web_poet.ApplyRule`` instead of
      ``web_poet.OverrideRule``.

* Provider for ``web_poet.ResponseUrl`` is added, which allows to access the
  response URL in the page object. This triggers a download unlike the provider
  for ``web_poet.RequestUrl``.
* Fixes the error when using ``scrapy shell`` while the
  ``scrapy_poet.InjectionMiddleware`` is enabled.
* Fixes and improvements on code and docs.


0.5.1 (2022-07-28)
------------------

Fixes the minimum web-poet version being 0.5.0 instead of 0.4.0.


0.5.0 (2022-07-28)
------------------

This release implements support for page object retries, introduced in web-poet
0.4.0.

To enable retry support, you need to configure a new spider middleware in your
Scrapy settings::

    SPIDER_MIDDLEWARES = {
        "scrapy_poet.RetryMiddleware": 275,
    }

web-poet 0.4.0 is now the minimum required version of web-poet.


0.4.0 (2022-06-20)
------------------

This release is backwards incompatible, following backwards-incompatible
changes in web-poet 0.2.0.

The main new feature is support for ``web-poet >= 0.2.0``, including
support for ``async def to_item`` methods, making additional requests
in the ``to_item`` method, new Page Object dependencies, and the new way
to configure overrides.

Changes in line with ``web-poet >= 0.2.0``:

* ``web_poet.HttpResponse`` replaces ``web_poet.ResponseData`` as a dependency
  to use.
* Additional requests inside Page Objects: a
  provider for ``web_poet.HttpClient``, as well as ``web_poet.HttpClient``
  backend implementation, which uses Scrapy downloader.
* ``callback_for`` now supports Page Objects which define ``async def to_item``
  method.
* Provider for ``web_poet.PageParams`` is added, which uses
  ``request.meta["page_params"]`` value.
* Provider for ``web_poet.RequestUrl`` is added, which allows to access the
  request URL in the page object without triggering the download.
* We have these **backward incompatible** changes since the
  ``web_poet.OverrideRule`` follow a different structure:

    * Deprecated ``PerDomainOverridesRegistry`` in lieu of the newer
      ``OverridesRegistry`` which provides a wide variety of features
      for better URL matching.
    * This resuls in a newer format in the ``SCRAPY_POET_OVERRIDES`` setting.

Other changes:

* New ``scrapy_poet/dummy_response_count`` value appears in Scrapy stats;
  it is the number of times ``DummyResponse`` is used instead of downloading
  the response as usual.
* ``scrapy.utils.reqser`` deprecated module is no longer used by scrapy-poet.

Dependency updates:

* The minimum supported Scrapy version is now ``2.6.0``.
* The minimum supported web-poet version is now ``0.2.0``.

0.3.0 (2022-01-28)
------------------

* Cache mechanism using ``SCRAPY_POET_CACHE``
* Fixed and improved docs
* removed support for Python 3.6
* added support for Python 3.10

0.2.1 (2021-06-11)
------------------

* Improved logging message for DummyResponse
* various internal cleanups

0.2.0 (2021-01-22)
------------------

* Overrides support

0.1.0 (2020-12-29)
------------------

* New providers interface

  * One provider can provide many types at once
  * Single instance during the whole spider lifespan
  * Registration is now explicit and done in the spider settings

* CI is migrated from Travis to Github Actions
* Python 3.9 support

0.0.3 (2020-07-19)
------------------

* Documentation improvements
* providers can now access various Scrapy objects:
  Crawler, Settings, Spider, Request, Response, StatsCollector

0.0.2 (2020-04-28)
------------------

The repository is renamed to ``scrapy-poet``, and split into two:

* ``web-poet`` (https://github.com/scrapinghub/web-poet) contains
  definitions and code useful for writing Page Objects for web
  data extraction - it is not tied to Scrapy;
* ``scrapy-poet`` (this package) provides Scrapy integration for such
  Page Objects.

API of the library changed in a backwards incompatible way;
see README and examples.

New features:

* ``DummyResponse`` annotation allows to skip downloading of scrapy Response.
* ``callback_for`` works for Scrapy disk queues if it is used to create
  a spider method (but not in its inline form)
* Page objects may require page objects as dependencies; dependencies are
  resolved recursively and built as needed.
* InjectionMiddleware supports ``async def`` and asyncio providers.


0.0.1 (2019-08-28)
------------------

Initial release.
