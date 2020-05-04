#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='scrapy-poet',
    version='0.0.2',
    description='Page Object pattern for Scrapy',
    long_description=open('README.rst').read() + "\n\n" + open('CHANGES.rst').read(),
    long_description_content_type="text/x-rst",
    author='Mikhail Korobov',
    author_email='kmike84@gmail.com',
    url='https://github.com/scrapinghub/scrapy-poet',
    packages=find_packages(exclude=['tests', 'example']),
    install_requires=[
        # We need to install pyasn1 before trying to install service_identity,
        # one of Scrapy's dependencies. This is a bug related to setuptools.
        #
        # https://github.com/pypa/setuptools/issues/498
        'pyasn1',
        'andi>=0.3',
        'attrs',
        'parsel',
        'scrapy>=2.1.0',
        'web-poet',
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Framework :: Scrapy',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)
