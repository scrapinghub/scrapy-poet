.. _`overrides`:

=========
Overrides
=========
This functionality opens the door to configure specific Page Objects depending
on the request URL domain. Please have a look to :ref:`intro-tutorial` to
learn the basics about overrides before digging deeper in the content of this
page.

Page Objects refinement
=======================

Any ``Injectable`` or page input can be overridden. But the overriding
mechanism stops for the children of any already overridden type. This opens
the door to refining existing Page Objects without getting trapped in a cyclic
dependency. For example, you might have an existing Page Object for book extraction:

.. code-block:: python

    class BookPage(ItemPage):
        def to_item(self):
            ...

Imagine this Page Object obtains its data from an external API.
Therefore, it is not holding the page HTML code.
But you want to extract an additional attribute (e.g. ``ISBN``) that
was not extracted by the original Page Object.
Using inheritance is not enough in this case, though.
No problem, you can just override it
using the following Page Object:

.. code-block:: python

    class ISBNBookPage(ItemWebPage):

        def __init__(self, response: ResponseData, book_page: BookPage):
            super().__init__(response)
            self.book_page = book_page

        def to_item(self):
            item = self.book_page.to_item()
            item['isbn'] = self.css(".isbn-class::text").get()
            return item

And then override it for a particular domain using ``settings.py``:

.. code-block:: python

    SCRAPY_POET_OVERRIDES = {
        "example.com": {
            BookPage: ISBNBookPage
        }
    }

This new Page Objects gets the original ``BookPage`` as dependency and enrich
the obtained item with the ISBN from the page HTML.

.. note::

    By design overrides rules are not applied to ``ISBNBookPage`` dependencies
    as it is an overridden type. If they were,
    it would end up in a cyclic dependency error because ``ISBNBookPage`` would
    depend on itself!

.. note::

    This is an alternative more compact way of writing the above Page Object using ``attr.s``:

    .. code-block:: python

        @attr.s(auto_attribs=True)
        class ISBNBookPage(ItemWebPage):
            book_page: BookPage

            def to_item(self):
                item = self.book_page.to_item()
                item['isbn'] = self.css(".isbn-class::text").get()
                return item

Overrides rules
---------------

The former example showed how to configure the overrides for a particular
domain. This is by far the most common case, but sometimes this is not
enough: in some cases you may require to have different overrides for some subdomains
(e.g. ``uk.somesite.com`` and ``us.somesite.com``); in other cases
you may want to have specific overrides for a subsection of a site
(e.g. ``somesite.com`` and ``somesite.com/deals``). This is entirely possible.
In fact, the examples presented above are already valid keys to be used
in the setting dictionary ``SCRAPY_POET_OVERRIDES``.

There is more information about how to configure ``SCRAPY_POET_OVERRIDES``
and the supported rules in :class:`scrapy_poet.overrides.HierarchicalOverridesRegistry`
documentation.


Overrides registry
==================

The overrides registry is responsible for informing whether there exists an
override for a particular type for a given response. The default overrides
registry allows to configure the overriding rules and reads the configuration
from settings ``SCRAPY_POET_OVERRIDES``. See :class:`scrapy_poet.overrides.HierarchicalOverridesRegistry`
for more information.

But the registry implementation can be changed at convenience. A different
registry implementation can be configured using the property
``SCRAPY_POET_OVERRIDES_REGISTRY`` in ``settings.py``. The new registry
must be a subclass of :class:`scrapy_poet.overrides.OverridesRegistryBase`
and must implement the method ``overrides_for``. As other Scrapy components,
it can be initialized from the ``from_crawler`` class method if implemented.
This might be handy to be able to access settings, stats, request meta, etc.

