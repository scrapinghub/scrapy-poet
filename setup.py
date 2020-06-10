from setuptools import setup, find_packages

setup(
    name='scrapy-poet',
    version='0.0.3',
    description='Page Object pattern for Scrapy',
    long_description=open('README.rst').read(),
    long_description_content_type="text/x-rst",
    author='Mikhail Korobov',
    author_email='kmike84@gmail.com',
    url='https://github.com/scrapinghub/scrapy-poet',
    packages=find_packages(exclude=['tests', 'example']),
    install_requires=['andi>=0.3', 'attrs', 'parsel', 'tenacity', 'web-poet'],
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
