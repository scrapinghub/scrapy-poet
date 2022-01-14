.. _`project_commands`:

================
Project Commands
================

``scrapy-poet`` extends some of Scrapy's commands for developer productivity.

startproject
============

The original ``scrapy startproject`` command would produce a project structure like:

.. code-block::

    my_project
    ├── my_project
    │   ├── spiders
    │   │   └── __init__.py
    │   ├── __init__.py
    │   ├── items.py
    │   ├── middlewares.py
    │   ├── pipelines.py
    │   └── settings.py
    └── scrapy.cfg

``scrapy-poet`` extends this further to setup:

    * a Page Objects directory in ``po/``
    * a test suite for Page Objects in ``tests/po/``

Invoking the same ``scrapy startproject`` would produce:

.. code-block::

    my_project
    ├── my_project
    │   ├── po
    │   │   ├── templates
    │   │   │   └── __init__.py
    │   │   └── __init__.py
    │   ├── spiders
    │   │   └── __init__.py
    │   ├── __init__.py
    │   ├── items.py
    │   ├── middlewares.py
    │   ├── pipelines.py
    │   └── settings.py
    ├── tests
    │   └── po
    │       ├── fixtures
    │       │   └── __init__.py
    │       └── __init__.py
    └── scrapy.cfg

override
========

Following the structure above, we can then use ``scrapy override`` to produce:


