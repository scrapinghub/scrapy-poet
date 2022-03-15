=========================
scrapy-poet documentation
=========================

``scrapy-poet`` allows to use `web-poet`_ Page Objects with Scrapy.

web-poet_ defines a standard for writing reusable and portable
extraction and crawling code; please check its docs_ to learn more.

By using ``scrapy-poet`` you'll be organizing the spider code in a different
way, which separates extraction and crawling logic from the I/O,
and from the Scrapy implementation details as well.
It makes the code more testable and reusable. Furthermore, it
opens the door to create generic spider code that works across sites.
Integrating a new site in the spider is then just a matter of write
a bunch of Page Objects for it.

``scrapy-poet`` also provides a way to integrate third-party APIs
(like `Splash`_ and `AutoExtract`_) with the spider, without losing
testability and reusability.
Concrete integrations are not provided by ``web-poet``, but
``scrapy-poet`` makes them possbile.

To get started, see :ref:`intro-install` and :ref:`intro-tutorial`.

:ref:`license` is BSD 3-clause.

.. _`AutoExtract`: https://scrapinghub.com/autoextract
.. _`Splash`: https://scrapinghub.com/splash
.. _`web-poet`: https://github.com/scrapinghub/web-poet
.. _docs: https://web-poet.readthedocs.io/en/stable/

.. toctree::
   :caption: Getting started
   :maxdepth: 1

   intro/install
   intro/basic-tutorial
   intro/advanced-tutorial

.. toctree::
   :caption: Advanced
   :maxdepth: 1

   overrides
   providers

.. toctree::
   :caption: All the rest
   :maxdepth: 1

   settings
   api_reference
   contributing
   changelog
   license
