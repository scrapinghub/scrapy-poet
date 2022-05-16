import os

from web_poet import HttpResponse, HttpResponseHeaders
from scrapy.http import Response
from scrapy.utils.project import project_data_dir, inside_project
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
    """
    return ".".join(tldextract.extract(url)[-2:])


def get_scrapy_data_path(createdir: bool = True, default_dir: str = ".scrapy") -> str:
    """Return a path to a folder where Scrapy is storing data.
    Usually that's a .scrapy folder inside the project.
    """
    # This code is extracted from scrapy.utils.project.data_path function,
    # which does too many things.
    path = project_data_dir() if inside_project() else default_dir
    if createdir:
        os.makedirs(path, exist_ok=True)
    return path


def scrapy_response_to_http_response(response: Response):
    """Convenience method to convert a ``scrapy.http.Response`` into a
    ``web_poet.HttpResponse``.
    """
    return HttpResponse(
        url=response.url,
        body=response.body,
        status=response.status,
        headers=HttpResponseHeaders.from_bytes_dict(response.headers),
    )
