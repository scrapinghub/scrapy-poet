from logging import getLogger

from scrapy.downloadermiddlewares.stats import DownloaderStats
from scrapy.settings import BaseSettings
from scrapy.utils.misc import load_object

from ._request_fingerprinter import ScrapyPoetRequestFingerprinter
from .downloadermiddlewares import DownloaderStatsMiddleware, InjectionMiddleware
from .spidermiddlewares import RetryMiddleware

logger = getLogger(__name__)


# https://github.com/zytedata/zyte-spider-templates/blob/1b72aa8912f6009d43bf87a5bd1920537d458744/zyte_spider_templates/_addon.py#L33C1-L88C37
def _replace_builtin(
    settings: BaseSettings, setting: str, builtin_cls: type, new_cls: type
) -> None:
    setting_value = settings[setting]
    if not setting_value:
        logger.warning(
            f"Setting {setting!r} is empty. Could not replace the built-in "
            f"{builtin_cls} entry with {new_cls}. Add {new_cls} manually to "
            f"silence this warning."
        )
        return

    if new_cls in setting_value:
        return
    for cls_or_path in setting_value:
        if isinstance(cls_or_path, str):
            _cls = load_object(cls_or_path)
            if _cls == new_cls:
                return

    builtin_entry: object = None
    for _setting_value in (setting_value, settings[f"{setting}_BASE"]):
        if builtin_cls in _setting_value:
            builtin_entry = builtin_cls
            pos = _setting_value[builtin_entry]
            break
        for cls_or_path in _setting_value:
            if isinstance(cls_or_path, str):
                _cls = load_object(cls_or_path)
                if _cls == builtin_cls:
                    builtin_entry = cls_or_path
                    pos = _setting_value[builtin_entry]
                    break
        if builtin_entry:
            break

    if not builtin_entry:
        logger.warning(
            f"Settings {setting!r} and {setting + '_BASE'!r} are both "
            f"missing built-in entry {builtin_cls}. Cannot replace it with {new_cls}. "
            f"Add {new_cls} manually to silence this warning."
        )
        return

    if pos is None:
        logger.warning(
            f"Built-in entry {builtin_cls} of setting {setting!r} is disabled "
            f"(None). Cannot replace it with {new_cls}. Add {new_cls} "
            f"manually to silence this warning. If you had replaced "
            f"{builtin_cls} with some other entry, you might also need to "
            f"disable that other entry for things to work as expected."
        )
        return

    settings[setting][builtin_entry] = None
    settings[setting][new_cls] = pos


# https://github.com/scrapy-plugins/scrapy-zyte-api/blob/a1d81d11854b420248f38e7db49c685a8d46d943/scrapy_zyte_api/addon.py#L12
def _setdefault(settings, setting, cls, pos):
    setting_value = settings[setting]
    if not setting_value:
        settings[setting] = {cls: pos}
        return
    if cls in setting_value:
        return
    for cls_or_path in setting_value:
        if isinstance(cls_or_path, str):
            _cls = load_object(cls_or_path)
            if _cls == cls:
                return
    settings[setting][cls] = pos


class Addon:
    def update_settings(self, settings: BaseSettings) -> None:
        settings.set(
            "REQUEST_FINGERPRINTER_CLASS",
            ScrapyPoetRequestFingerprinter,
            priority="addon",
        )
        _setdefault(settings, "DOWNLOADER_MIDDLEWARES", InjectionMiddleware, 543)
        _setdefault(settings, "SPIDER_MIDDLEWARES", RetryMiddleware, 275)
        _replace_builtin(
            settings,
            "DOWNLOADER_MIDDLEWARES",
            DownloaderStats,
            DownloaderStatsMiddleware,
        )
