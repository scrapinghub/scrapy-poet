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

        def __init__(self, response: HttpResponse, book_page: BookPage):
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

    This is an alternative more compact way of writing the above Page Object
    using ``attr.define``:

    .. code-block:: python

        @attr.define
        class ISBNBookPage(ItemWebPage):
            book_page: BookPage

            def to_item(self):
                item = self.book_page.to_item()
                item['isbn'] = self.css(".isbn-class::text").get()
                return item


Overrides registry
==================

The overrides registry is responsible for informing whether there exists an
override for a particular type for a given response. The default overrides
registry keeps a map of overrides for each domain and read this configuration
from settings ``SCRAPY_POET_OVERRIDES`` as has been seen in the :ref:`intro-tutorial`
example.

But the registry implementation can be changed at convenience. A different
registry implementation can be configured using the property
``SCRAPY_POET_OVERRIDES_REGISTRY`` in ``settings.py``. The new registry
must be a subclass of ``scrapy_poet.overrides.OverridesRegistryBase``
and must implement the method ``overrides_for``. As other Scrapy components,
it can be initialized from the ``from_crawler`` class method if implemented.
This might be handy to be able to access settings, stats, request meta, etc.

