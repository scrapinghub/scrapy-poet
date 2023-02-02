.. _settings:

Settings
========

Configuring the settings denoted below would follow the usual methods used by
Scrapy.


SCRAPY_POET_PROVIDERS
---------------------

Default: ``{}``

A ``dict`` wherein the **keys** would be the providers available for your Scrapy
project while the **values** denotes the priority of the provider.

More info on this at this section: :ref:`providers`.


SCRAPY_POET_OVERRIDES
---------------------

Deprecated. Use ``SCRAPY_POET_RULES`` instead.

SCRAPY_POET_RULES
-----------------

Default: :meth:`web_poet.default_registry.get_rules()`

.. warning::

    Although ``SCRAPY_POET_RULES`` already has values from the ``default_registry``,
    make sure you call :func:`web_poet.rules.consume_modules` if you're using
    other rules from other external packages.

    Example:

    .. code-block:: python

        from web_poet import default_registry, consume_modules

        # The consume_modules() must be called first if you need to properly import
        # rules from other packages. Otherwise, it can be omitted.
        # More info about this caveat on web-poet docs.
        consume_modules("external_package_A", "another_ext_package.lib")

        # To get all of the Override Rules that were declared via annotations.
        SCRAPY_POET_RULES = default_registry.get_rules()


Accepts a ``List[ApplyRule]`` which sets the rules to use.

There are sections dedicated for this at :ref:`intro-tutorial` and
:ref:`rules-from-web-poet`.


SCRAPY_POET_CACHE
-----------------

Default: ``None``

The caching mechanism in the **providers** can be enabled by either setting this
to ``True`` which configures the file path of the cache into a ``.scrapy/`` dir
in your `local Scrapy project`.

On the other hand, you can also set this as a ``str`` pointing to any path relative
to your `local Scrapy project`.


SCRAPY_POET_CACHE_GZIP
----------------------

Default: ``True``

Enables compression of the cached data using the **Gzip**. `Recommended` to be
set to ``True`` in order to preserve disk space when caching.


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


SCRAPY_POET_TESTS_DIR
---------------------

Default: ``fixtures``

Sets the location where the ``savefixture`` command creates tests.

More info at :ref:`testing`.
