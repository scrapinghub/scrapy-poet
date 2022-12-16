import warnings

from .registry import OverridesRegistry  # noqa: F401

msg = "The 'scrapy_poet.overrides' module has been moved into 'scrapy_poet.registry'."
warnings.warn(msg, DeprecationWarning, stacklevel=2)
