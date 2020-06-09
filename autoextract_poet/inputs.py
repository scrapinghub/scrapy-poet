from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AutoExtractResponseData:
    """Represent an AutoExtract API response containing returned data."""
    data: Optional[Dict[str, Any]]


@dataclass
class AutoExtractProductResponseData(AutoExtractResponseData):
    """Represent an AutoExtract Product response."""
    pass


@dataclass
class AutoExtractProductListResponseData(AutoExtractResponseData):
    """Represent an AutoExtract Product List response."""
    pass
