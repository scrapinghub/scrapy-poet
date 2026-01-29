from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="scrapy-poet",
    version=Path("scrapy_poet", "VERSION").read_text().strip(),
    description="Page Object pattern for Scrapy",
    long_description=Path("README.rst").read_text(encoding="utf-8"),
    long_description_content_type="text/x-rst",
    author="Mikhail Korobov",
    author_email="kmike84@gmail.com",
    url="https://github.com/scrapinghub/scrapy-poet",
    packages=find_packages(exclude=["tests", "example"]),
    entry_points={
        "scrapy.commands": ["savefixture = scrapy_poet.commands:SaveFixtureCommand"]
    },
    package_data={"scrapy_poet": ["VERSION"]},
    python_requires=">=3.10",
    install_requires=[
        "andi >= 0.6.0",
        "attrs >= 21.3.0",
        "parsel >= 1.5.0",
        "scrapy >= 2.6.0",
        "sqlitedict >= 1.5.0",
        "time_machine >= 2.7.1",
        "twisted >= 18.9.0",
        "url-matcher >= 0.2.0",
        "web-poet >= 0.17.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Framework :: Scrapy",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
)
