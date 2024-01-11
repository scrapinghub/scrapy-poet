try:
    from scrapy.utils.request import RequestFingerprinter  # NOQA
except ImportError:
    from typing import TYPE_CHECKING

    if not TYPE_CHECKING:
        ScrapyPoetRequestFingerprinter = None
else:
    import hashlib
    import json
    from functools import cached_property
    from logging import getLogger
    from typing import Callable, Dict, List, Optional, get_args, get_origin
    from weakref import WeakKeyDictionary

    from scrapy import Request
    from scrapy.crawler import Crawler
    from scrapy.settings.default_settings import REQUEST_FINGERPRINTER_CLASS
    from scrapy.utils.misc import create_instance, load_object
    from web_poet import (
        HttpClient,
        HttpRequest,
        HttpRequestBody,
        HttpRequestHeaders,
        PageParams,
        RequestUrl,
        Stats,
    )
    from web_poet.utils import get_fq_class_name

    from scrapy_poet import InjectionMiddleware
    from scrapy_poet.injection import get_callback

    logger = getLogger(__name__)

    def _serialize_dep(cls):
        try:
            from typing import Annotated
        except ImportError:
            pass
        else:
            if get_origin(cls) is Annotated:
                annotated, *annotations = get_args(cls)
                return f"{_serialize_dep(annotated)}{repr(annotations)}"
        return get_fq_class_name(cls)

    class ScrapyPoetRequestFingerprinter:

        IGNORED_UNANNOTATED_DEPS = {
            # These dependencies are tools for page objects that should have no
            # bearing on the request itself.
            HttpClient,
            Stats,
            # These dependencies do not impact the fingerprint as dependencies,
            # it is their value on the request itself that should have an
            # impact on the request fingerprint.
            HttpRequest,
            HttpRequestBody,
            HttpRequestHeaders,
            PageParams,
            RequestUrl,
        }

        @classmethod
        def from_crawler(cls, crawler):
            return cls(crawler)

        def __init__(self, crawler: Crawler) -> None:
            settings = crawler.settings
            self._base_request_fingerprinter = create_instance(
                load_object(
                    settings.get(
                        "SCRAPY_POET_REQUEST_FINGERPRINTER_BASE_CLASS",
                        REQUEST_FINGERPRINTER_CLASS,
                    )
                ),
                settings=crawler.settings,
                crawler=crawler,
            )
            self._callback_cache: Dict[Callable, Optional[bytes]] = {}
            self._request_cache: "WeakKeyDictionary[Request, bytes]" = (
                WeakKeyDictionary()
            )
            self._crawler: Crawler = crawler
            self._saw_unserializable_page_params = False

        @cached_property
        def _injector(self):
            middlewares = self._crawler.engine.downloader.middleware.middlewares
            for middleware in middlewares:
                if isinstance(middleware, InjectionMiddleware):
                    return middleware.injector
            raise RuntimeError(
                "scrapy_poet.InjectionMiddleware not found at run time, has it "
                "been configured in the DOWNLOADER_MIDDLEWARES setting?"
            )

        def _get_deps(self, request: Request) -> Optional[List[str]]:
            """Return a JSON-serializable structure that uniquely identifies the
            dependencies requested by the request, or None if dependency injection
            is not required."""
            plan = self._injector.build_plan(request)
            deps = {dep for dep, params in plan[:-1]} - self.IGNORED_UNANNOTATED_DEPS
            if not deps:
                return None
            return sorted([_serialize_dep(cls) for cls in deps])

        def get_deps_key(self, request: Request) -> Optional[bytes]:
            """Return a JSON array as bytes that uniquely identifies the
            dependencies requested through scrapy-poet injection that could
            impact the request, or None if there are no such dependencies."""
            callback = get_callback(request, self._crawler.spider)
            if callback in self._callback_cache:
                return self._callback_cache[callback]

            deps = self._get_deps(request)
            if not deps:
                self._callback_cache[callback] = None
                return None

            deps_key = json.dumps(deps, sort_keys=True).encode()
            self._callback_cache[callback] = deps_key
            return self._callback_cache[callback]

        def serialize_page_params(self, request: Request) -> Optional[bytes]:
            """Return a JSON object as bytes that represents the page params,
            or None if there are no page params or they are not
            JSON-serializable."""
            page_params = request.meta.get("page_params", None)
            if not page_params:
                return None

            try:
                return json.dumps(page_params, sort_keys=True).encode()
            except TypeError:
                if not self._saw_unserializable_page_params:
                    self._saw_unserializable_page_params = True
                    logger.warning(
                        f"Cannot serialize page params {page_params!r} of "
                        f"request {request} as JSON. This can be an issue if "
                        f"you have requests that are identical except for "
                        f"their page params, because unserializable page "
                        f"params are treated the same as missing or empty "
                        f"page params for purposes of request fingerprinting "
                        f"(see "
                        f"https://docs.scrapy.org/en/latest/topics/request-response.html#request-fingerprints). "
                        f"This will be the only warning about this issue, "
                        f"other requests might be also affected."
                    )
                return None

        def fingerprint(self, request: Request) -> bytes:
            if request in self._request_cache:
                return self._request_cache[request]

            fingerprint = self._base_request_fingerprinter.fingerprint(request)
            deps_key = self.get_deps_key(request)
            serialized_page_params = self.serialize_page_params(request)
            if deps_key is None and serialized_page_params is None:
                return fingerprint
            if deps_key is not None:
                fingerprint += deps_key
            if serialized_page_params is not None:
                fingerprint += serialized_page_params

            self._request_cache[request] = hashlib.sha1(fingerprint).digest()
            return self._request_cache[request]
