from typing import TYPE_CHECKING

try:
    from scrapy.utils.request import RequestFingerprinter  # NOQA
except ImportError:
    if not TYPE_CHECKING:
        ScrapyPoetRequestFingerprinter = None
else:
    import hashlib
    import json
    from functools import cached_property
    from typing import Callable, Dict, List, Optional
    from weakref import WeakKeyDictionary

    from scrapy import Request
    from scrapy.crawler import Crawler
    from scrapy.settings.default_settings import REQUEST_FINGERPRINTER_CLASS
    from scrapy.utils.misc import create_instance, load_object

    from scrapy_poet import InjectionMiddleware
    from scrapy_poet.injection import get_callback

    class ScrapyPoetRequestFingerprinter:
        @classmethod
        def from_crawler(cls, crawler):
            return cls(crawler)

        def __init__(self, crawler: Crawler) -> None:
            settings = crawler.settings
            self._fallback_request_fingerprinter = create_instance(
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
            return [repr(cls) for cls in root_deps.values()]

        def fingerprint_deps(self, request: Request) -> Optional[bytes]:
            """Return a fingerprint based on dependencies requested through
            scrapy-poet injection, or None if no injection was requested."""
            callback = get_callback(request, self._crawler.spider)
            if callback in self._callback_cache:
                return self._callback_cache[callback]

            deps = self._get_deps(request)
            if deps is None:
                return None

            deps_key = json.dumps(deps, sort_keys=True).encode()
            self._callback_cache[callback] = hashlib.sha1(deps_key).digest()
            return self._callback_cache[callback]

        def fingerprint(self, request: Request) -> bytes:
            if request in self._request_cache:
                return self._request_cache[request]
            fingerprint = self._fallback_request_fingerprinter.fingerprint(request)
            deps_fingerprint = self.fingerprint_deps(request)
            if deps_fingerprint is None:
                return fingerprint
            fingerprints = fingerprint + deps_fingerprint
            self._request_cache[request] = hashlib.sha1(fingerprints).digest()
            return self._request_cache[request]
