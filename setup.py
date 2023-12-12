from os.path import dirname, join

from setuptools import find_packages, setup

with open(join(dirname(__file__), "scrapy_poet/VERSION"), "rb") as f:
    version = f.read().decode("ascii").strip()

setup(
    name="scrapy-poet",
    version=version,
    description="Page Object pattern for Scrapy",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author="Mikhail Korobov",
    author_email="kmike84@gmail.com",
    url="https://github.com/scrapinghub/scrapy-poet",
    packages=find_packages(exclude=["tests", "example"]),
    entry_points={
        "scrapy.commands": ["savefixture = scrapy_poet.commands:SaveFixtureCommand"]
    },
    package_data={"scrapy_poet": ["VERSION"]},
    python_requires=">=3.8",
    install_requires=[
        "andi >= 0.4.1",
        "attrs >= 21.3.0",
        "parsel >= 1.5.0",
        "scrapy >= 2.6.0",
        "sqlitedict >= 1.5.0",
        "time_machine >= 2.2.0",
        "twisted >= 18.9.0",
        "url-matcher >= 0.2.0",
        "web-poet >= 0.15.1",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Framework :: Scrapy",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
