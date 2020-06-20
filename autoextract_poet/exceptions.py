from dataclasses import dataclass

from autoextract_poet.query import Query


@dataclass
class QueryLevelError(Exception):

    query: Query
    msg: str
