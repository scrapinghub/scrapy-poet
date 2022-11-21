import abc
import gzip
import pickle
import sqlite3
from typing import Any

import sqlitedict


class _Cache(abc.ABC):
    @abc.abstractmethod
    def __getitem__(self, fingerprint: str) -> Any:
        pass

    @abc.abstractmethod
    def __setitem__(self, fingerprint: str, value) -> None:
        pass

    def close(self) -> None:  # noqa: B027
        pass


class SqlitedictCache(_Cache):
    """Stores dependencies from Providers in a persistent local storage using
    https://github.com/RaRe-Technologies/sqlitedict.
    """

    def __init__(self, path: str, *, compressed=True):
        self.path = path
        self.compressed = compressed
        tablename = "responses_gzip" if compressed else "responses"
        self.db = sqlitedict.SqliteDict(
            path,
            tablename=tablename,
            autocommit=True,
            encode=self.encode,
            decode=self.decode,
        )

    def encode(self, obj: Any) -> memoryview:
        # based on sqlitedict.encode
        data = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
        if self.compressed:
            data = gzip.compress(data, compresslevel=3)
        return sqlite3.Binary(data)

    def decode(self, obj: Any) -> Any:
        # based on sqlitedict.decode
        data = bytes(obj)
        if self.compressed:
            # gzip is slightly less efficient than raw zlib, but it does
            # e.g. crc checks out of box
            data = gzip.decompress(data)
        return pickle.loads(data)

    def __str__(self) -> str:
        return (  # pragma: no cover
            f"SqlitedictCache <{self.db.filename} | "
            f"compressed: {self.compressed} | "
            f"{len(self.db)} records>"
        )

    def __repr__(self) -> str:
        return f"SqlitedictCache({self.path!r}, compressed={self.compressed})"  # pragma: no cover

    def __getitem__(self, fingerprint: str) -> Any:
        return self.db[fingerprint]

    def __setitem__(self, fingerprint: str, value: Any) -> None:
        self.db[fingerprint] = value

    def close(self) -> None:
        self.db.close()
