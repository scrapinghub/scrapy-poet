.. _rules-from-web-poet:

===================
Rules from web-poet
===================

scrapy-poet fully supports the functionalities of :class:`web_poet.rules.ApplyRule`.
It has its own registry called :class:`scrapy_poet.registry.OverridesAndItemRegistry`
which provides functionalties for:

    * Returning the page object override if it exists for a given URL.
    * Returning the page object capable of producing an item for a given URL.

A list of :class:`web_poet.rules.ApplyRule` can be configured by passing it
to the ``SCRAPY_POET_RULES`` setting.

In this section, we go over its ``instead_of`` parameter for overrides and
``to_return`` for item returns. However, please make sure you also read web-poet's
:ref:`rules-intro` tutorial to see all of the expected behaviors of the rules.


Overrides
=========
This functionality opens the door to configure specific Page Objects depending
on the request URL domain. Please have a look to :ref:`intro-tutorial` to
learn the basics about overrides before digging deeper in the content of this
page.

.. tip::

    Some real-world examples on this topic can be found in:

    - `Example 1 <https://github.com/scrapinghub/scrapy-poet/blob/master/example/example/spiders/books_04_overrides_01.py>`_:
      small example
    - `Example 2 <https://github.com/scrapinghub/scrapy-poet/blob/master/example/example/spiders/books_04_overrides_02.py>`_:
      larger example
    - `Example 3 <https://github.com/scrapinghub/scrapy-poet/blob/master/example/example/spiders/books_04_overrides_03.py>`_:
      rules using :py:func:`web_poet.handle_urls` decorator and retrieving them
      via :py:meth:`web_poet.rules.RulesRegistry.get_rules`


Page Objects refinement
-----------------------

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

    class ISBNBookPage(WebPage):

        def __init__(self, response: HttpResponse, book_page: BookPage):
            super().__init__(response)
            self.book_page = book_page

        def to_item(self):
            item = self.book_page.to_item()
            item['isbn'] = self.css(".isbn-class::text").get()
            return item

And then override it for a particular domain using ``settings.py``:

.. code-block:: python

    SCRAPY_POET_RULES = [
        ApplyRule("example.com", use=ISBNBookPage, instead_of=BookPage)
    ]

This new Page Object gets the original ``BookPage`` as dependency and enrich
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
        class ISBNBookPage(WebPage):
            book_page: BookPage

            def to_item(self):
                item = self.book_page.to_item()
                item['isbn'] = self.css(".isbn-class::text").get()
                return item


Overrides rules
---------------

The following example configures an override that is only applied for book pages
from ``books.toscrape.com``:

.. code-block:: python

    from web_poet import ApplyRule


    SCRAPY_POET_RULES = [
        ApplyRule(
            for_patterns=Patterns(
                include=["books.toscrape.com/cataloge/*index.html|"],
                exclude=["/catalogue/category/"]),
            use=MyBookPage,
            instead_of=BookPage
        )
    ]

Note how category pages are excluded by using a ``exclude`` pattern.
You can find more information about the patterns syntax in the
`url-matcher <https://url-matcher.readthedocs.io/en/stable/>`_
documentation.


Decorate Page Objects with the rules
------------------------------------

Having the rules along with the Page Objects is a good idea,
as you can identify with a single sight what the Page Object is doing
along with where it is applied. This can be done by decorating the
Page Objects with :py:func:`web_poet.handle_urls` provided by `web-poet`_.

.. tip::
    Make sure to read the :external:ref:`rules-intro` Tutorial section of
    `web-poet`_ to learn all of its other functionalities that is not covered
    in this section.

Let's see an example:

.. code-block:: python

    from web_poet import handle_urls


    @handle_urls("toscrape.com", instead_of=BookPage)
    class BTSBookPage(BookPage):

        def to_item(self):
            return {
                'url': self.url,
                'name': self.css("title::text").get(),
            }

The :py:func:`web_poet.handle_urls` decorator in this case is indicating that
the class ``BSTBookPage`` should be used instead of ``BookPage``
for the domain ``toscrape.com``.

In order to configure the ``scrapy-poet`` overrides automatically
using these annotations, you can directly interact with `web-poet`_'s
``default_registry`` (an instance of :py:class:`web_poet.rules.RulesRegistry`).

For example:

.. code-block:: python

    from web_poet import default_registry, consume_modules

    # The consume_modules() must be called first if you need to properly import
    # rules from other packages. Otherwise, it can be omitted.
    # More info about this caveat on web-poet docs.
    consume_modules("external_package_A", "another_ext_package.lib")

    # To get all of the Override Rules that were declared via annotations.
    SCRAPY_POET_RULES = default_registry.get_rules()

The :py:meth:`web_poet.rules.RulesRegistry.get_rules` method of the
``default_registry`` above returns ``List[ApplyRule]`` that were declared
using `web-poet`_'s :py:func:`web_poet.handle_urls` annotation. This is much
more convenient that manually defining all of the :py:class:`web_poet.ApplyRule`.

Take note that since ``SCRAPY_POET_RULES`` is structured as
``List[ApplyRule]``, you can easily modify it later on if needed.

.. note::

    For more info and advanced features of `web-poet`_'s :py:func:`web_poet.handle_urls`
    and its registry, kindly read the `web-poet <https://web-poet.readthedocs.io>`_
    documentation, specifically its :external:ref:`rules-intro` tutorial
    section.


Item Returns
============

scrapy-poet also supports a convenient way of asking for items directly. This
is made possible by the ``to_return`` parameter of :class:`web_poet.rules.ApplyRule`.
The ``to_return`` specifies which item a page object is capable of returning for
a given URL.

Let's check out an example:

.. code-block:: python

    import attrs
    import scrapy
    from web_poet import WebPage, handle_urls, field


    @attrs.define
    class Product:
        name: str


    @handle_urls("example.com")
    @attrs.define
    class ProductPage(WebPage[Product]):

        @field
        def name(self) -> str:
            return self.css("h1.name ::text").get("")


    class MySpider(scrapy.Spider):
        name = "myspider"

        def start_requests(self):
            yield scrapy.Request(
                "https://example.com/products/some-product", self.parse
            )

        # We can directly ask for the item here instead of the page object.
        def parse(self, response, item: Product):
            return item

From this example, we can see that:

    * Spider callbacks can directly ask for items as dependencies.
    * The ``Product`` item instance directly comes from ``ProductPage``.
    * This is made possible by the ``ApplyRule("example.com", use=ProductPage,
      to_return=Product)`` instance created from the ``@handle_urls`` decorator
      on ``ProductPage``.

.. note::

    The slightly longer alternative way to do this is by declaring the page
    object itself as the dependency and then calling its ``.to_item()`` method.
    For example:

    .. code-block:: python

        @handle_urls("example.com")
        @attrs.define
        class ProductPage(WebPage[Product]):
            product_image_page: ProductImagePage

            @field
            def name(self) -> str:
                return self.css("h1.name ::text").get("")

            @field
            async def image(self) -> Image:
                return await self.product_image_page.to_item()


        class MySpider(scrapy.Spider):
            name = "myspider"

            def start_requests(self):
                yield scrapy.Request(
                    "https://example.com/products/some-product", self.parse
                )

            async def parse(self, response, product_page: ProductPage):
                return await product_page.to_item()

For more information about all the expected behavior for the ``to_return``
parameter in :class:`web_poet.rules.ApplyRule`, check out web-poet's tutorial
regarding :ref:`rules-item-class-example`.


Registry
========

As mentioned above, scrapy-poet has its own registry called
:class:`scrapy_poet.registry.OverridesAndItemRegistry`.
This registry implementation can be changed if needed. A different registry can
be configured by passing its class path to the ``SCRAPY_POET_REGISTRY`` setting.
Such registries must be a subclass of :class:`scrapy_poet.registry.OverridesRegistryBase`
and must implement the :meth:`scrapy_poet.registry.OverridesRegistryBase.overrides_for` method.
