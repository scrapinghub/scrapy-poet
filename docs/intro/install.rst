.. _intro-install:

============
Installation
============

Installing scrapy-poet
======================

``scrapy-poet`` is a Scrapy extension that runs on Python 3.8 and above.

If you’re already familiar with installation of Python packages, you can install
``scrapy-poet`` and its dependencies from PyPI with:

::

    pip install scrapy-poet

Scrapy 2.6.0 or above is required and it has to be installed separately.

Configuring the project
=======================

To use ``scrapy-poet``, enable its middlewares in the ``settings.py`` file
of your Scrapy project:

.. code-block:: python

    DOWNLOADER_MIDDLEWARES = {
        "scrapy_poet.InjectionMiddleware": 543,
    }
    SPIDER_MIDDLEWARES = {
        "scrapy_poet.RetryMiddleware": 275,
    }
    REQUEST_FINGERPRINTER_CLASS = "scrapy_poet.ScrapyPoetRequestFingerprinter"

Things that are good to know
============================

``scrapy-poet`` is written in pure Python and depends on a few key Python packages
(among others):

- web-poet_, core library used for Page Object pattern
- andi_, provides annotation-based dependency injection
- parsel_, responsible for css and xpath selectors

.. _web-poet: https://github.com/scrapinghub/web-poet
.. _andi: https://github.com/scrapinghub/andi
.. _parsel: https://github.com/scrapy/parsel
