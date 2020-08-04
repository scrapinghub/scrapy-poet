from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ResponseData:
    """AutoExtract API response containing returned data."""
    data: Optional[Dict[str, Any]]


@dataclass
class ProductResponseData(ResponseData):
    """AutoExtract Product response."""
    pass


@dataclass
class ProductListResponseData(ResponseData):
    """AutoExtract Product List response."""
    pass
