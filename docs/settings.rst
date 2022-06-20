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

Default: ``None``

Mapping of overrides for each domain. The format of the such ``dict`` mapping
depends on the currently set Registry. The default is currently 
:class:`~.OverridesRegistry`. This can be overriden by the setting below:
``SCRAPY_POET_OVERRIDES_REGISTRY``.

There are sections dedicated for this at :ref:`intro-tutorial` and :ref:`overrides`.


SCRAPY_POET_OVERRIDES_REGISTRY
------------------------------

Defaut: ``None``

Sets an alternative Registry to replace the default :class:`~.OverridesRegistry`.
To use this, set a ``str`` which denotes the absolute object path of the new
Registry.

More info at :ref:`overrides`.


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
