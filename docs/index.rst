.. scrapy-poet documentation master file, created by
   sphinx-quickstart on Tue Apr 28 16:45:10 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=========================
scrapy-poet documentation
=========================

scrapy-poet easily integrates Page Objects created using `web-poet`_ with
Scrapy through the configuration of a dependency injection middleware.

The goal of this project is to make reusable Page Objects that separates
extraction logic from crawling. They could be easily tested and distributed
across different projects. Also, they could make use of different backends,
for example, acquiring data from `Splash`_ and `AutoExtract`_ API.

Please, see also our :ref:`intro-install` and our :ref:`intro-tutorial`
for a quick start.

:ref:`license` is BSD 3-clause.

.. _`AutoExtract`: https://scrapinghub.com/autoextract
.. _`Splash`: https://scrapinghub.com/splash
.. _`web-poet`: https://github.com/scrapinghub/web-poet

.. toctree::
   :caption: Getting started
   :hidden:

   intro/install
   intro/tutorial

.. toctree::
   :caption: Reference
   :maxdepth: 2
   :hidden:

   advanced
   api_reference
   contributing
   changelog
   license
