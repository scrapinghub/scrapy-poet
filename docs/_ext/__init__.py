def setup(app):
    # https://stackoverflow.com/a/13663325
    #
    # Scrapy’s
    # https://github.com/scrapy/scrapy/blob/dba37674e6eaa6c2030c8eb35ebf8127cd488062/docs/_ext/scrapydocs.py#L90C16-L110C6
    app.add_crossref_type(
        directivename="setting",
        rolename="setting",
        indextemplate="pair: %s; setting",
    )
    app.add_crossref_type(
        directivename="signal",
        rolename="signal",
        indextemplate="pair: %s; signal",
    )
    app.add_crossref_type(
        directivename="command",
        rolename="command",
        indextemplate="pair: %s; command",
    )
    app.add_crossref_type(
        directivename="reqmeta",
        rolename="reqmeta",
        indextemplate="pair: %s; reqmeta",
    )
