=========
Changelog
=========

0.25.0 (2024-12-27)
-------------------

* Added Python 3.13 support, removed Python 3.8 support.

* Improved Scrapy 2.12 support (typing, deprecations).

0.24.0 (2024-10-10)
-------------------

* When the :ref:`dynamic dependencies <dynamic-deps>` are annotated with
  :data:`typing.Annotated`, the keys in the resulting :class:`~.DynamicDeps`
  instance are now not annotated.

* Improved the error message when passing incorrect values in the ``"inject"``
  meta key.

* Fixed documentation builds with ``sphinx-rtd-theme`` 3.0.0+.

0.23.0 (2024-07-18)
-------------------

* Added support for :ref:`specifying callback dependencies dynamically
  <dynamic-deps>`.

0.22.6 (2024-07-03)
-------------------

* Raising :class:`~web_poet.exceptions.core.Retry` now also works as expected
  when callbacks ask for an item instead of asking for its page object.

0.22.5 (2024-06-27)
-------------------

* When :class:`~web_poet.exceptions.core.Retry` is raised with a message, that
  message now becomes the retry reason, replacing the default
  (``page_object_retry``).

0.22.4 (2024-06-10)
-------------------

* :ref:`Additional requests <additional-requests>`, when mapped to
  :class:`scrapy.Request <scrapy.http.Request>` objects, now get their
  ``dont_filter`` parameter set to ``True``, to ask downloader middlewares like
  :class:`~scrapy.downloadermiddlewares.offsite.OffsiteMiddleware` not to drop
  those requests.

0.22.3 (2024-04-25)
-------------------

* :func:`scrapy_poet.utils.testing.make_crawler` now respects setting
  priorities when it receives a :class:`~scrapy.settings.Settings` object
  instead of a :class:`dict`.

0.22.2 (2024-04-24)
-------------------

* :class:`~scrapy_poet.page_input_providers.HttpRequestProvider`, added in
  0.17.0, is now actually enabled by default.

0.22.1 (2024-03-07)
-------------------

* Fixed ``scrapy savefixture`` not finding page object modules when used
  outside a Scrapy project.

0.22.0 (2024-03-04)
-------------------

* Now requires ``web-poet >= 0.17.0`` and ``time_machine >= 2.7.1``.

* Removed ``scrapy_poet.AnnotatedResult``, use
  :class:`web_poet.annotated.AnnotatedInstance` instead.

* Added support for annotated dependencies to the ``scrapy savefixture``
  command.

* Test improvements.

0.21.0 (2024-02-08)
-------------------

* Added a ``.weak_cache`` to :class:`scrapy_poet.injection.Injector` which
  stores instances created by providers as long as the :class:`scrapy.Request
  <scrapy.http.Request>` exists.

* Fixed the incorrect value of ``downloader/response_count`` in the stats due
  to additional counting of :class:`scrapy_poet.api.DummyResponse`.

* Fixed the detection of :class:`scrapy_poet.api.DummyResponse` when some type
  hints are annotated using strings.

0.20.1 (2024-01-24)
-------------------

* :class:`~scrapy_poet.ScrapyPoetRequestFingerprinter` now supports item
  dependencies.

0.20.0 (2024-01-15)
-------------------

* Add :class:`~scrapy_poet.ScrapyPoetRequestFingerprinter`, a request
  fingerprinter that uses request dependencies in the fingerprint generation.

0.19.0 (2023-12-26)
-------------------

* Now requires ``andi >= 0.6.0``.

* Changed the implementation of resolving and building item dependencies from
  page objects. Now ``andi`` custom builders are used to create a single plan
  that includes building page objects and items. This fixes problems such as
  providers being called multiple times.

  * :class:`~scrapy_poet.page_input_providers.ItemProvider` is now no-op. It's
    no longer enabled by default and users should also stop enabling it.
  * ``PageObjectInputProvider.allow_prev_instances`` and code related to it
    were removed so custom providers may need updating.

* Fixed some tests.

0.18.0 (2023-12-12)
-------------------

* Now requires ``andi >= 0.5.0``.

* Add support for dependency metadata via ``typing.Annotated`` (requires
  Python 3.9+).

0.17.0 (2023-12-11)
-------------------

* Now requires ``web-poet >= 0.15.1``.

* :class:`~web_poet.page_inputs.http.HttpRequest` dependencies are now
  supported, via :class:`~scrapy_poet.page_input_providers.HttpRequestProvider`
  (enabled by default).

* Enable :class:`~scrapy_poet.page_input_providers.StatsProvider`, which
  provides :class:`~web_poet.page_inputs.stats.Stats` dependencies, by default.

* More robust disabling of
  :class:`~scrapy_poet.downloadermiddlewares.InjectionMiddleware` in the
  ``scrapy savefixture`` command.

* Official support for Python 3.12.

0.16.1 (2023-11-02)
-------------------

* Fix the bug that caused requests produced by
  :class:`~scrapy_poet.page_input_providers.HttpClientProvider` to
  be treated as if they need arguments of the ``parse`` callback as
  dependencies, which could cause returning an empty response and/or making
  extra provider calls.

0.16.0 (2023-09-26)
-------------------

* Now requires ``time_machine >= 2.2.0``.

* ``ItemProvider`` now supports page objects that declare a dependency on the
  same type of item that they return, as long as there is an earlier page
  object input provider that can provide such dependency.

* Fix running tests with Scrapy 2.11.

0.15.1 (2023-09-15)
-------------------

* :ref:`scrapy-poet stats <stats>` now also include counters for injected
  dependencies (``poet/injector/<dependency import path>``).

* All scrapy-poet stats  that used to be prefixed with ``scrapy-poet/`` are now
  prefixed with ``poet/`` instead.

0.15.0 (2023-09-12)
-------------------

* Now requires ``web-poet >= 0.15.0``.

* :external+web-poet:ref:`Web-poet stats <stats>` are now :ref:`supported
  <stats>`.


0.14.0 (2023-09-08)
-------------------

* Python 3.7 support has been dropped.

* Caching is now built on top of web-poet serialization, extending caching
  support to additional inputs, while making our code simpler, more reliable,
  and more future-proof.

  This has resulted in a few backward-incompatible changes:

  * The ``scrapy_poet.page_input_providers.CacheDataProviderMixin`` mixin class
    has been removed. Providers no longer need to use it or reimplement its
    methods.

  * The ``SCRAPY_POET_CACHE_GZIP`` setting has been removed.

* Added ``scrapy_poet.utils.open_in_browser``, an alternative to
  ``scrapy.utils.response.open_in_browser`` that supports scrapy-poet.

* Fixed some documentation links.


0.13.0 (2023-05-08)
-------------------

* Now requires ``web-poet >= 0.12.0``.

* The ``scrapy savefixture`` command now uses the adapter from the
  ``SCRAPY_POET_TESTS_ADAPTER`` setting to save the fixture.

* Fix a typo in the docs.


0.12.0 (2023-04-26)
-------------------

* Now requires ``web-poet >= 0.11.0``.

* The ``scrapy savefixture`` command can now generate tests that expect that
  ``to_item()`` raises a specific exception (only
  :class:`web_poet.exceptions.PageObjectAction` and its descendants are
  expected).

* Fixed an error when using ``scrapy shell`` with
  :class:`scrapy_poet.InjectionMiddleware` enabled.

* Add a ``twine check`` CI check.


0.11.0 (2023-03-17)
-------------------

* The ``scrapy savefixture`` command can now generate a fixture :ref:`using an
  existing spider <fixture-spiders>`.


0.10.1 (2023-03-03)
-------------------

* More robust time freezing in ``scrapy savefixture`` command.


0.10.0 (2023-02-24)
-------------------

* Now requires ``web-poet >= 0.8.0``.

* The ``savefixture`` command now also saves requests made via the
  :class:`web_poet.page_inputs.client.HttpClient` dependency and their
  responses.


0.9.0 (2023-02-17)
------------------

* Added support for item classes which are used as dependencies in page objects
  and spider callbacks. The following is now possible:

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
          # ✨ NEW: The page object can ask for items as dependencies. An instance
          # of ``Image`` is injected behind the scenes by calling the ``.to_item()``
          # method of ``ProductImagePage``.
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
                  "https://example.com/products/some-product", self.parse_product
              )

          # ✨ NEW: We can directly use the item here instead of the page object.
          def parse_product(self, response: DummyResponse, item: Product) -> Product:
              return item


  In line with this, the following new features were made:

    * New :class:`scrapy_poet.page_input_providers.ItemProvider` which makes the
      usage above possible.

    * An item class is now supported by :func:`scrapy_poet.callback_for`
      alongside the usual page objects. This means that it won't raise a
      :class:`TypeError` anymore when not passing a subclass of
      :class:`web_poet.pages.ItemPage`.

    * New exception: :class:`scrapy_poet.injection_errors.ProviderDependencyDeadlockError`.
      This is raised when it's not possible to create the dependencies due to
      a deadlock in their sub-dependencies, e.g. due to a circular dependency
      between page objects.

* New setting named ``SCRAPY_POET_RULES`` having a default value of
  :meth:`web_poet.default_registry.get_rules <web_poet.rules.RulesRegistry.get_rules>`.
  This deprecates ``SCRAPY_POET_OVERRIDES``.

* New setting named ``SCRAPY_POET_DISCOVER`` to ensure that ``SCRAPY_POET_RULES``
  have properly loaded all intended rules annotated with the ``@handle_urls``
  decorator.

* New utility functions in ``scrapy_poet.utils.testing``.

* The ``frozen_time`` value inside the :ref:`test fixtures <testing>` won't
  contain microseconds anymore.

* Supports the new :func:`scrapy.http.request.NO_CALLBACK` introduced in
  **Scrapy 2.8**. This means that the :ref:`pitfalls` (introduced in
  ``scrapy-poet==0.7.0``) doesn't apply when you're using Scrapy >= 2.8, unless
  you're using third-party middlewares which directly uses the downloader to add
  :class:`scrapy.Request <scrapy.http.Request>` instances with callback set to
  ``None``. Otherwise, you need to set the callback value to
  :func:`scrapy.http.request.NO_CALLBACK`.

* Fix the :class:`TypeError` that's raised when using Twisted <= 21.7.0 since
  scrapy-poet was using ``twisted.internet.defer.Deferred[object]`` type
  annotation before which was not subscriptable in the early Twisted versions.

* Fix the ``twisted.internet.error.ReactorAlreadyInstalledError`` error raised
  when using the ``scrapy savefixture`` command and Twisted < 21.2.0 is installed.

* Fix test configuration that doesn't follow the intended commands and dependencies
  in these tox environments: ``min``, ``asyncio-min``, and ``asyncio``. This
  ensures that page objects using ``asyncio`` should work properly, alongside
  the minimum specified Twisted version.

* Various improvements to tests and documentation.

* Backward incompatible changes:

    * For the :class:`scrapy_poet.page_input_providers.PageObjectInputProvider`
      base class:

        * It now accepts an instance of :class:`scrapy_poet.injection.Injector`
          in its constructor instead of :class:`scrapy.crawler.Crawler`. Although
          you can still access the :class:`scrapy.crawler.Crawler` via the
          ``Injector.crawler`` attribute.

        * :meth:`scrapy_poet.page_input_providers.PageObjectInputProvider.is_provided`
          is now an instance method instead of a class method.

    * The :class:`scrapy_poet.injection.Injector`'s attribute and constructor
      parameter  called ``overrides_registry`` is now simply called ``registry``.

    * Removed the ``SCRAPY_POET_OVERRIDES_REGISTRY`` setting which overrides the
      default registry.

    * The ``scrapy_poet.overrides`` module which contained ``OverridesRegistryBase``
      and ``OverridesRegistry`` has now been removed. Instead, scrapy-poet directly
      uses :class:`web_poet.rules.RulesRegistry`.

      Everything should pretty much the same except for
      :meth:`web_poet.rules.RulesRegistry.overrides_for` now accepts :class:`str`,
      :class:`web_poet.page_inputs.http.RequestUrl`, or
      :class:`web_poet.page_inputs.http.ResponseUrl` instead of
      :class:`scrapy.http.Request`.

    * This also means that the registry doesn't accept tuples as rules anymore.
      Only :class:`web_poet.rules.ApplyRule` instances are allowed. The same goes
      for ``SCRAPY_POET_RULES`` (and the deprecated ``SCRAPY_POET_OVERRIDES``).

    * The following type aliases have been removed:

        * ``scrapy_poet.overrides.RuleAsTuple``
        * ``scrapy_poet.overrides.RuleFromUser``


0.8.0 (2023-01-24)
------------------

* Now requires ``web-poet >= 0.7.0`` and ``time_machine``.

* Added a ``savefixture`` command that creates a test for a page object.
  See :ref:`testing` for more information.


0.7.0 (2023-01-17)
------------------

* Fixed the issue where a new page object containing a new response data is not
  properly created when :class:`web_poet.exceptions.core.Retry` is raised.

* In order for the above fix to be possible, overriding the callback dependencies
  created by **scrapy-poet** via :attr:`scrapy.http.Request.cb_kwargs` is now
  unsupported. This is a **backward incompatible** change.

* Fixed the broken
  :meth:`scrapy_poet.page_input_providers.HttpResponseProvider.fingerprint`
  which errors out when running a Scrapy job using the ``SCRAPY_POET_CACHE``
  enabled.

* Improved behavior when ``spider.parse()`` method arguments are supposed
  to be provided by **scrapy-poet**. Previously, it was causing
  unnecessary work in unexpected places like
  :class:`scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware`,
  :class:`scrapy.pipelines.images.ImagesPipeline` or
  :class:`scrapy.pipelines.files.FilesPipeline`. It is also a reason
  :class:`web_poet.page_inputs.client.HttpClient` might not be working
  in page objects. Now these cases are detected, and a warning is issued.

  As of Scrapy 2.7, it is not possible to fix the issue completely
  in **scrapy-poet**. Fixing it would require Scrapy changes; some 3rd party
  libraries may also need to be updated.

  .. note::

      The root of the issue is that when request.callback is ``None``,
      ``parse()`` callback is assumed normally. But sometimes callback=None
      is used when :class:`scrapy.http.Request` is added to the Scrapy's
      downloader directly, in which case no callback is used. Middlewares,
      including **scrapy-poet**'s, can't distinguish between these two cases,
      which causes all kinds of issues.

  We recommend all **scrapy-poet** users to modify their code to
  avoid the issue. Please **don't** define ``parse()``
  method with arguments which are supposed to be filled by **scrapy-poet**,
  and rename the existing ``parse()`` methods if they have such arguments.
  Any other name is fine. It avoids all possible issues, including
  incompatibility with 3rd party middlewares or pipelines.

  See the new :ref:`pitfalls` documentation for more information.

  There are backwards-incompatible changes related to this issue.
  They only affect you if you don't follow the advice of not using ``parse()``
  method with **scrapy-poet**.

    * When the ``parse()`` method has its response argument annotated with
      :class:`scrapy_poet.api.DummyResponse`, for instance:
      ``def parse(self, response: DummyResponse)``, the response is downloaded
      instead of being skipped.

    * When the ``parse()`` method has dependencies that are provided by
      **scrapy-poet**, the :class:`scrapy_poet.downloadermiddlewares.InjectionMiddleware` won't
      attempt to build any dependencies anymore.

      This causes the following code to have this error ``TypeError: parse()
      missing 1 required positional argument: 'page'.``:

        .. code-block:: python

            class MySpider(scrapy.Spider):
                name = "my_spider"
                start_urls = ["https://books.toscrape.com"]

                def parse(self, response: scrapy.http.Response, page: MyPage):
                    ...

* :func:`scrapy_poet.injection.is_callback_requiring_scrapy_response` now accepts
  an optional ``raw_callback`` parameter meant to represent the actual callback
  attribute value of :class:`scrapy.http.Request` since the original ``callback``
  parameter could be normalized to the spider's ``parse()`` method when the
  :class:`scrapy.http.Request` has ``callback`` set to ``None``.

* Official support for Python 3.11

* Various updates and improvements on docs and examples.

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
