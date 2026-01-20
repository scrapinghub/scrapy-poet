.. _dynamic-deps:

====================
Dynamic dependencies
====================

Normally the dependencies for a callback are specified statically, as type
hints for its arguments:

.. code-block:: python

    import scrapy


    class BooksSpider(scrapy.Spider):
        ...

        async def start(self):
            yield scrapy.Request("http://books.toscrape.com/", self.parse_book)

        def parse_book(self, response, book_page: BookPage, other_dep: OtherDep):
            ...

In some cases some or all of the dependencies need to be specified dynamically
instead, e.g. because they need to be different for different requests using
the same callback. You can use :class:`scrapy_poet.DynamicDeps
<scrapy_poet.injection.DynamicDeps>` for this. If you add a callback argument
with this type you can pass a list of additional dependency types in the
request meta dictionary using the "inject" key:

.. code-block:: python

    import scrapy


    class BooksSpider(scrapy.Spider):
        ...

        async def start(self):
            yield scrapy.Request(
                "http://books.toscrape.com/",
                self.parse_book,
                meta={"inject": [OtherDep]},
            )

        def parse_book(self, response, book_page: BookPage, dynamic: DynamicDeps):
            # access the dynamic dependency values by their type:
            other_dep = dynamic[OtherDep]
            ...
            # or get them and their types at the run time:
            for dep_type, dep in dynamic.items():
                if dep_type is OtherDep:
                    ...

The types passed this way are used in the dependency resolution as usual, with
the created instances available in the :class:`scrapy_poet.DynamicDeps
<scrapy_poet.injection.DynamicDeps>` instance, which is a dictionary with
dependency types as keys and their instances as values.
