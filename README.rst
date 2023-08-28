===========
scrapy-poet
===========

.. image:: https://img.shields.io/pypi/v/scrapy-poet.svg
   :target: https://pypi.python.org/pypi/scrapy-poet
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/scrapy-poet.svg
   :target: https://pypi.python.org/pypi/scrapy-poet
   :alt: Supported Python Versions

.. image:: https://github.com/scrapinghub/scrapy-poet/workflows/tox/badge.svg
   :target: https://github.com/scrapinghub/scrapy-poet/actions
   :alt: Build Status

.. image:: https://codecov.io/github/scrapinghub/scrapy-poet/coverage.svg?branch=master
   :target: https://codecov.io/gh/scrapinghub/scrapy-poet
   :alt: Coverage report

.. image:: https://readthedocs.org/projects/scrapy-poet/badge/?version=stable
   :target: https://scrapy-poet.readthedocs.io/en/stable/?badge=stable
   :alt: Documentation Status

``scrapy-poet`` is the `web-poet`_ Page Object pattern implementation for Scrapy.
``scrapy-poet`` allows to write spiders where extraction logic is separated from the crawling one.
With ``scrapy-poet`` is possible to make a single spider that supports many sites with
different layouts.

Read the `documentation <https://scrapy-poet.readthedocs.io>`_  for more information.

License is BSD 3-clause.

* Documentation: https://scrapy-poet.readthedocs.io
* Source code: https://github.com/scrapinghub/scrapy-poet
* Issue tracker: https://github.com/scrapinghub/scrapy-poet/issues

.. _`web-poet`: https://github.com/scrapinghub/web-poet


Quick Start
***********

Installation
============

.. code-block::

    pip install scrapy-poet

Requires **Python 3.8+** and **Scrapy >= 2.6.0**.

Usage in a Scrapy Project
=========================

Add the following inside Scrapy's ``settings.py`` file:

.. code-block:: python

    DOWNLOADER_MIDDLEWARES = {
        "scrapy_poet.InjectionMiddleware": 543,
    }
    SPIDER_MIDDLEWARES = {
        "scrapy_poet.RetryMiddleware": 275,
    }

Developing
==========

Setup your local Python environment via:

1. `pip install -r requirements-dev.txt`
2. `pre-commit install`

Now everytime you perform a `git commit`, these tools will run against the
staged files:

* `black`
* `isort`
* `flake8`

You can also directly invoke `pre-commit run --all-files` or `tox -e linters`
to run them without performing a commit.
