.. _`intro-install`:

==================
Installation guide
==================

Installing scrapy-poet
======================

scrapy-poet is a Scrapy extension that runs on Python 3.6 and above.

If you’re already familiar with installation of Python packages, you can install
scrapy-poet and its dependencies from PyPI with:

::

    pip install scrapy-poet

Scrapy 2.1.0 or above is required and it has to be installed separately.

Things that are good to know
============================

scrapy-poet is written in pure Python and depends on a few key Python packages
(among others):

- web-poet_, core library used for Page Object pattern
- andi_, provides annotation-based dependency injection
- parsel_, responsible for css and xpath selectors

.. _web-poet: https://github.com/scrapinghub/web-poet
.. _andi: https://github.com/scrapinghub/andi
.. _parsel: https://github.com/scrapinghub/parsel
