#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name='scrapy-po',
    version='0.0.1',
    description='Page Object pattern for Scrapy',
    long_description=open('README.rst').read() + "\n\n" + open('CHANGES.rst').read(),
    author='Mikhail Korobov',
    author_email='kmike84@gmail.com',
    url='https://github.com/scrapinghub/scrapy-po',
    packages=find_packages(exclude=['tests', 'example']),
    install_requires=['andi>=0.3', 'attrs', 'parsel'],
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
    ],
)
