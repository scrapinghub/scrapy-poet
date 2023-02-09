import os

# Note that tox.ini should only set the REACTOR env variable when running
# pytest with "--reactor=asyncio".
if os.environ.get("REACTOR", "") == "asyncio":
    from scrapy.utils.reactor import install_reactor

    install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
