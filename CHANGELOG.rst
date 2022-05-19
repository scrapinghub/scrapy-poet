=========
Changelog
=========

TBR
---

* Use the new ``web_poet.HttpResponse`` which replaces ``web_poet.ResponseData``.
* We have these **backward incompatible** changes since the
  ``web_poet.OverrideRule`` follow a different structure:

    * Deprecated ``PerDomainOverridesRegistry`` in lieu of the newer
      ``OverridesRegistry`` which provides a wide variety of features
      for better URL matching.
    * This resuls in a newer format in the ``SCRAPY_POET_OVERRIDES`` setting.


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
