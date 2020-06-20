from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AutoExtractResponseData:
    """AutoExtract API response containing returned data."""
    data: Optional[Dict[str, Any]]


@dataclass
class ProductResponseData(AutoExtractResponseData):
    """AutoExtract Product response."""
    pass


@dataclass
class ProductListResponseData(AutoExtractResponseData):
    """AutoExtract Product List response."""
    pass
