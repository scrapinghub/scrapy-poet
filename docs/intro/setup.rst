.. _setup:

=====
Setup
=====

.. _intro-install:

Install
=======

.. code-block:: bash

    pip install scrapy-poet


Enable
======

.. _addon:

Configure the scrapy-poet add-on to enable it:

.. code-block:: python
    :caption: settings.py

    ADDONS = {
        "scrapy_poet.Addon": 300,
    }

.. _addon-changes:

This is what the add-on changes:

-   In :setting:`DOWNLOADER_MIDDLEWARES`:

    -   Sets :class:`~scrapy_poet.InjectionMiddleware` with value ``543``.

    -   Sets :class:`~scrapy_poet.HtmlMetadataMiddleware` with value ``585``.

    -   Replaces
        :class:`scrapy.downloadermiddlewares.stats.DownloaderStats`
        with :class:`scrapy_poet.DownloaderStatsMiddleware`.

-   Sets :setting:`REQUEST_FINGERPRINTER_CLASS` to
    :class:`~scrapy_poet.ScrapyPoetRequestFingerprinter`.

-   In :setting:`SPIDER_MIDDLEWARES`, sets
    :class:`~scrapy_poet.RetryMiddleware` with value ``275``.


Configure
=========

Declare the :setting:`SCRAPY_POET_DISCOVER` setting with a list of modules that
define page objects, so that they can be loaded at run-time.

A best practice is to create a ``pages/`` folder in your Scrapy project, a
sibling of your ``spiders/`` folder, add an empty ``__init__.py`` file to it
to make it a Python module, and declare its import path in the setting:

.. code-block:: python
    :caption: settings.py

    SCRAPY_POET_DISCOVER = ["myproject.pages"]
