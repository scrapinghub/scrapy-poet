=========
Changelog
=========

TBR
---

* Improved ``scrapy-poet`` behavior when ``spider.parse()`` method
  arguments are annotated. Previously, they were causing unnecessary work
  in unexpected places like
  :class:`scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware`,
  :class:`scrapy.pipelines.images.ImagesPipeline` or
  :class:`scrapy.pipelines.files.FilesPipeline`. It is also a reason
  :class:`web_poet.page_inputs.client.HttpClient` might not be working in page objects.
  Now these cases are detected, and a warning is issued.

  As of Scrapy 2.7, it is not possible to fix the issue completely
  in scrapy-poet. Fixing it would require Scrapy changes; some 3rd party
  libraries may also need to be updated.

  .. note::

      The root of the issue is that when request.callback is None, ``parse``
      callback is assumed normally. But sometimes callback=None is used
      when :class:`scrapy.http.Request` is added to the Scrapy's downloader
      directly, in which case no callback is used. Middlewares, including
      **scrapy-poet**'s, can't distinguish between these two cases, which causes
      all kinds of issues.

  We recommend all **scrapy-poet** users to modify their code to
  avoid the issue. Please **don't** define ``parse``
  method with arguments which are supposed to be filled by ``scrapy-poet``,
  and rename the existing ``parse`` methods if they have such arguments.
  Any other name is fine. It avoids all possible issues, including
  incompatibility with 3rd party middlewares or pipelines.

  See the new :ref:`pitfalls` documentation for more information.

  There are backwards-incompatible changes related to this issue.
  They only affect you if you don't follow the advice of not using ``parse``
  method with **scrapy-poet**.

    * When the ``parse()`` method has its response argument annotated with
      :class:`scrapy_poet.api.DummyResponse`, for instance:
      ``def parse(self, response: DummyResponse)``, the response is downloaded
      instead of being skipped.

    * When the ``parse()`` method has dependencies that are provided by
      ``scrapy-poet``, the :class:`scrapy_poet.downloadermiddlewares.InjectionMiddleware` won't
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
