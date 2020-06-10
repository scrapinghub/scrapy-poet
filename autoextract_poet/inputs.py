from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ResponseData:
    """Represent an AutoExtract API response containing returned data."""
    data: Optional[Dict[str, Any]]


@dataclass
class ProductResponseData(ResponseData):
    """Represent an AutoExtract Product response."""
    pass


@dataclass
class ProductListResponseData(ResponseData):
    """Represent an AutoExtract Product List response."""
    pass
