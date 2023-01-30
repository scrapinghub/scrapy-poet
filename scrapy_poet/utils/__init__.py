import os
from typing import Any, Collection, Optional, Type
from warnings import warn

try:
    from typing import Annotated  # Python 3.9+
except ImportError:
    from typing_extensions import _AnnotatedAlias as Annotated

from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.utils.project import inside_project, project_data_dir
from web_poet import HttpRequest, HttpResponse, HttpResponseHeaders, ItemPage
from web_poet.fields import get_fields_dict

from scrapy_poet.api import NotPickFields, PickFields


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


def http_request_to_scrapy_request(request: HttpRequest, **kwargs) -> Request:
    return Request(
        url=str(request.url),
        method=request.method,
        headers=request.headers,
        body=request.body,
        **kwargs,
    )


def scrapy_response_to_http_response(response: Response) -> HttpResponse:
    """Convenience method to convert a ``scrapy.http.Response`` into a
    ``web_poet.HttpResponse``.
    """
    kwargs = {}
    encoding = getattr(response, "_encoding", None)
    if encoding:
        kwargs["encoding"] = encoding
    return HttpResponse(
        url=response.url,
        body=response.body,
        status=response.status,
        headers=HttpResponseHeaders.from_bytes_dict(response.headers),
        **kwargs,
    )


def get_origin(cls: Any) -> Any:
    """Offers backward compatibility for Python 3.7 since ``typing.get_origin(tp)``
    is only available starting on 3.8.

    Moreover, ``typing_extensions.get_origin`` doesn't work well with
    ``typing_extensions.Annotated``.
    """
    return getattr(cls, "__origin__", ())


def _normalize_annotated_cls(cls: Any) -> Any:
    """Returns the type ``T`` in ``typing.Annotated[T, x]``, if applicable.

    See: https://peps.python.org/pep-0593/
    """
    if isinstance(cls, Annotated):
        cls = get_origin(cls)
    return cls


def _derive_fields(annotation: Any, page_obj: ItemPage) -> Optional[Collection[str]]:
    """Returns a Collection of strings representing the fields names to extract
    from the page object based on the annotations specified on its item:

        - ``typing.Annotated[T, PickFields(x, ...)]``
        - ``typing.Annotated[T, NotPickFields(x, ...)]``
    """

    if not isinstance(annotation, Annotated):
        return None

    def _use_fields(_fields, values):
        if _fields:
            raise ValueError("PickFields and NotPickFields should not be used together")
        return values

    fields = []

    for metadata in annotation.__metadata__:
        if isinstance(metadata, PickFields):
            fields = _use_fields(fields, metadata.fields)

        if isinstance(metadata, NotPickFields):
            if metadata.fields:
                fields = _use_fields(
                    fields, get_fields_dict(page_obj).keys() - set(metadata.fields)
                )

    return fields


def create_registry_instance(cls: Type, crawler: Crawler):
    if "SCRAPY_POET_OVERRIDES" in crawler.settings:
        msg = (
            "The SCRAPY_POET_OVERRIDES setting is deprecated. "
            "Use SCRAPY_POET_RULES instead."
        )
        warn(msg, DeprecationWarning, stacklevel=2)
    rules = crawler.settings.getlist(
        "SCRAPY_POET_RULES",
        crawler.settings.getlist("SCRAPY_POET_OVERRIDES", []),
    )
    return cls(rules=rules)
