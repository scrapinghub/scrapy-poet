from dataclasses import dataclass
from typing import List


@dataclass
class QueryLevelError(Exception):

    query: List
    msg: str
