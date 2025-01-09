# Scrapy settings for example project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from example.autoextract import AutoextractProductProvider

BOT_NAME = "example"

SPIDER_MODULES = ["example.spiders"]
NEWSPIDER_MODULE = "example.spiders"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

ADDONS = {
    "scrapy_poet.Addon": 300,
}

SCRAPY_POET_PROVIDERS = {AutoextractProductProvider: 500}
