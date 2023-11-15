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

    from scrapy_poet import InjectionMiddleware
    from scrapy_poet.injection import get_callback

    def _serialize_dep(cls):
        try:
            from typing import Annotated
        except ImportError:
            pass
        else:
            if get_origin(cls) is Annotated:
                annotated, *annotations = get_args(cls)
                return f"{_serialize_dep(annotated)}{repr(annotations)}"
        return f"{cls.__module__}.{cls.__qualname__}"

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
            self._callback_cache: Dict[Callable, bytes] = {}
            self._request_cache: "WeakKeyDictionary[Request, bytes]" = (
                WeakKeyDictionary()
            )
            self._crawler: Crawler = crawler

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
            root_deps = plan[-1][1]
            if not root_deps:
                return None
            return sorted(
                [
                    _serialize_dep(cls)
                    for cls in root_deps.values()
                    if cls not in self.IGNORED_UNANNOTATED_DEPS
                ]
            )

        def fingerprint_deps(self, request: Request) -> Optional[bytes]:
            """Return a fingerprint based on dependencies requested through
            scrapy-poet injection, or None if no injection was requested."""
            callback = get_callback(request, self._crawler.spider)
            if callback in self._callback_cache:
                return self._callback_cache[callback]

            deps = self._get_deps(request)
            if not deps:
                return None

            deps_key = json.dumps(deps, sort_keys=True).encode()
            self._callback_cache[callback] = hashlib.sha1(deps_key).digest()
            return self._callback_cache[callback]

        def fingerprint(self, request: Request) -> bytes:
            if request in self._request_cache:
                return self._request_cache[request]
            fingerprint = self._base_request_fingerprinter.fingerprint(request)
            deps_fingerprint = self.fingerprint_deps(request)
            if deps_fingerprint is None:
                return fingerprint
            fingerprints = fingerprint + deps_fingerprint
            self._request_cache[request] = hashlib.sha1(fingerprints).digest()
            return self._request_cache[request]
