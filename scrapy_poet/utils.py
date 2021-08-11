import re
from urllib.parse import urlsplit

from tldextract import tldextract


def get_domain(url):
    """
    Return the domain without any subdomain

    >>> get_domain("http://blog.example.com")
    'example.com'
    >>> get_domain("http://www.example.com")
    'example.com'
    >>> get_domain("http://deeper.blog.example.co.uk")
    'example.co.uk'
    >>> get_domain("http://127.0.0.1")
    '127.0.0.1'
    """
    return ".".join(el for el in tldextract.extract(url)[-2:] if el)


# Is IP Regex, from https://www.oreilly.com/library/view/regular-expressions-cookbook/9780596802837/ch07s16.html
_IS_IP_ADDRESS_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)


def url_hierarchical_str(url: str) -> str:
    """
    Return a string that represents the url in a way that its
    components are ordered by its hierarchical importance. That is, the top
    level domain is the most important, so it is the fist element in the string.
    Then goes the rest of the levels in the domain, the port and finally the path.

    Can be very useful to verify if a URL is a subpath of the other just
    by checking if one url hierarchical str is the prefix of the other.

    Trailing slash for the path is removed and the query and the fragment
    are ignored.

    >>> url_hierarchical_str("http://")
    ''
    >>> url_hierarchical_str("http://example.com:343")
    'com.example.:343'
    >>> url_hierarchical_str("http://example.com:343/")
    'com.example.:343'
    >>> url_hierarchical_str("http://WWW.example.com:343/")
    'com.example.:343'
    >>> url_hierarchical_str("http://www.EXAMPLE.com:343/?id=23")
    'com.example.:343'
    >>> url_hierarchical_str("http://www.example.com:343/page?id=23")
    'com.example.:343/page'
    >>> url_hierarchical_str("http://www.example.com:343/page?id=23;params#fragment")
    'com.example.:343/page'
    >>> url_hierarchical_str("http://127.0.0.1:80/page?id=23;params#fragment")
    '127.0.0.1./page'
    >>> url_hierarchical_str("https://127.0.0.1:443/page?id=23;params#fragment")
    '127.0.0.1./page'
    >>> url_hierarchical_str("https://127.0.0.1:333/page?id=23;params#fragment")
    '127.0.0.1.:333/page'
    >>> url_hierarchical_str("http://example.com:333/path/to/something")
    'com.example.:333/path/to/something'
    >>> url_hierarchical_str("mailto://example.com")
    Traceback (most recent call last):
    ...
    ValueError: Unsupported scheme for URL mailto://example.com
    >>> url_hierarchical_str("http://example.com:k34")  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: Port could not be cast to integer value as 'k34'
    >>> url_hierarchical_str("/path")
    Traceback (most recent call last):
    ...
    ValueError: Unsupported scheme for URL /path
    """
    parts = urlsplit(url.strip())
    scheme, netloc, path, query, fragment = parts
    if scheme.lower() not in ["http", "https"]:
        raise ValueError(f"Unsupported scheme for URL {url}")
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port and parts.port not in [80, 443] else ""

    if not _IS_IP_ADDRESS_RE.match(host):
        # Remove www and reverse the domains
        dom_secs = host.split(".")
        if dom_secs:
            if dom_secs[0] == "www":
                dom_secs = dom_secs[1:]
        host = ".".join(reversed(dom_secs))
    if host:
        host += "."

    if path.endswith("/"):
        path = path[:-1]

    return f"{host}{port}{path}"

