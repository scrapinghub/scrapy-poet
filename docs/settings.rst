.. _settings:

Settings
========

Configuring the settings denoted below would follow the usual methods used by
Scrapy.


.. setting:: SCRAPY_POET_CACHE

SCRAPY_POET_CACHE
-----------------

Default: ``None``

The caching mechanism in the **providers** can be enabled by either setting this
to ``True`` which configures the file path of the cache into a ``.scrapy/`` dir
in your `local Scrapy project`.

On the other hand, you can also set this as a ``str`` pointing to any path relative
to your `local Scrapy project`.


.. setting:: SCRAPY_POET_CACHE_ERRORS

SCRAPY_POET_CACHE_ERRORS
------------------------

Default: ``False``

When this is set to ``True``, any error that arises when retrieving dependencies from
providers would be cached. This could be useful in cases during local development
wherein you outright know that retrieving the dependency would fail and would
choose to ignore it. Caching such errors would reduce the waiting time when
developing Page Objects.

It's `recommended` to set this off into ``False`` by default since you might miss
out on sporadic errors.


.. setting:: SCRAPY_POET_DISCOVER

SCRAPY_POET_DISCOVER
--------------------

Default: ``[]``

A list of packages/modules (i.e. ``List[str]``) which scrapy-poet will look for
page objects annotated with the :func:`web_poet.handle_urls` decorator. Each
package/module is passed into
:func:`web_poet.consume_modules <web_poet.rules.consume_modules>` where each
module from a package is recursively loaded.

This ensures that when using the default value of ``SCRAPY_POET_RULES`` set to
:meth:`web_poet.default_registry.get_rules() <web_poet.rules.RulesRegistry.get_rules>`,
it should contain all the intended rules.

Note that it's also possible for ``SCRAPY_POET_RULES`` to have rules not specified
in ``SCRAPY_POET_DISCOVER`` (e.g. when the annotated page objects are inside your
Scrapy project). However, it's recommended to still use ``SCRAPY_POET_DISCOVER``
to ensure all the intended rules are properly loaded.


.. setting:: SCRAPY_POET_OVERRIDES

SCRAPY_POET_OVERRIDES
---------------------

Deprecated. Use ``SCRAPY_POET_RULES`` instead.


.. setting:: SCRAPY_POET_PROVIDERS

SCRAPY_POET_PROVIDERS
---------------------

Default: ``{}``

A ``dict`` wherein the **keys** would be the providers available for your Scrapy
project while the **values** denotes the priority of the provider.

More info on this at this section: :ref:`providers`.


.. setting:: SCRAPY_POET_REQUEST_FINGERPRINTER_BASE_CLASS

SCRAPY_POET_REQUEST_FINGERPRINTER_BASE_CLASS
--------------------------------------------

The default value is the default value of the ``REQUEST_FINGERPRINTER_CLASS``
setting for the version of Scrapy currently installed (e.g.
``"scrapy.utils.request.RequestFingerprinter"``).

You can assign a request fingerprinter class to this setting to configure a
custom request fingerprinter class to use for requests.

This class is used to generate a base fingerprint for a request. If that
request uses dependency injection, that fingerprint is then modified to account
for requested dependencies. Otherwise, the fingerprint is used as is.

.. note:: Annotations of :ref:`annotated dependencies <annotated>` are
    serialized with :func:`repr` for fingerprinting purposes. If you find a
    real-world scenario where this is a problem, please `open an issue
    <https://github.com/scrapinghub/scrapy-poet/issues>`_.


.. setting:: SCRAPY_POET_RULES

SCRAPY_POET_RULES
-----------------

Default: :meth:`web_poet.default_registry.get_rules()
<web_poet.rules.RulesRegistry.get_rules>`

Accepts a ``List[ApplyRule]`` which sets the rules to use.

.. warning::

    Although ``SCRAPY_POET_RULES`` already has values set from the return value of
    :meth:`web_poet.default_registry.get_rules() <web_poet.rules.RulesRegistry.get_rules>`,
    make sure to also set the ``SCRAPY_POET_DISCOVER`` setting below.

There are sections dedicated for this at :ref:`intro-tutorial` and
:ref:`rules-from-web-poet`.


.. setting:: SCRAPY_POET_TESTS_ADAPTER

SCRAPY_POET_TESTS_ADAPTER
-------------------------

Default: ``None``

Sets the class, or its import path, that will be used as an adapter in the
generated test fixtures.

More info at :ref:`fixture-adapter`.


.. setting:: SCRAPY_POET_TESTS_DIR

SCRAPY_POET_TESTS_DIR
---------------------

Default: ``fixtures``

Sets the location where the ``savefixture`` command creates tests.

More info at :ref:`testing`.
