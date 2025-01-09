.. _setup:

=====
Setup
=====

.. _intro-install:

Install from PyPI::

    pip install scrapy-poet

Then configure:

-   For Scrapy ≥ 2.10, install the add-on:

    .. code-block:: python
        :caption: settings.py

        ADDONS = {
            "scrapy_poet.Addon": 300,
        }

    .. _addon-changes:

    This is what the add-on changes:

    -   In :setting:`DOWNLOADER_MIDDLEWARES`:

        -   Sets :class:`~scrapy_poet.InjectionMiddleware` with value ``543``.

        -   Replaces
            :class:`scrapy.downloadermiddlewares.stats.DownloaderStats`
            with :class:`scrapy_poet.DownloaderStatsMiddleware`.

    -   Sets :setting:`REQUEST_FINGERPRINTER_CLASS` to
        :class:`~scrapy_poet.ScrapyPoetRequestFingerprinter`.

    -   In :setting:`SPIDER_MIDDLEWARES`, sets
        :class:`~scrapy_poet.RetryMiddleware` with value ``275``.

-   For Scrapy < 2.10, manually apply :ref:`the add-on changes
    <addon-changes>`. For example:

    .. code-block:: python
        :caption: settings.py

        DOWNLOADER_MIDDLEWARES = {
            "scrapy_poet.InjectionMiddleware": 543,
            "scrapy.downloadermiddlewares.stats.DownloaderStats": None,
            "scrapy_poet.DownloaderStatsMiddleware": 850,
        }
        REQUEST_FINGERPRINTER_CLASS = "scrapy_poet.ScrapyPoetRequestFingerprinter"
        SPIDER_MIDDLEWARES = {
            "scrapy_poet.RetryMiddleware": 275,
        }
