import abc
import gzip
import pickle
import sqlite3

import sqlitedict


class _Cache(abc.ABC):

    @abc.abstractmethod
    def __getitem__(self, fingerprint: str):
        pass

    @abc.abstractmethod
    def __setitem__(self, fingerprint: str, value) -> None:
        pass

    def close(self):
        pass


class SqlitedictCache(_Cache):

    def __init__(self, path, *, compressed=True):
        self.compressed = compressed
        tablename = 'responses_gzip' if compressed else 'responses'
        self.db = sqlitedict.SqliteDict(path,
                                        tablename=tablename,
                                        autocommit=True,
                                        encode=self.encode,
                                        decode=self.decode)

    def encode(self, obj):
        # based on sqlitedict.encode
        data = pickle.dumps(obj, pickle.HIGHEST_PROTOCOL)
        if self.compressed:
            data = gzip.compress(data, compresslevel=3)
        return sqlite3.Binary(data)

    def decode(self, obj):
        # based on sqlitedict.decode
        data = bytes(obj)
        if self.compressed:
            # gzip is slightly less efficient than raw zlib, but it does
            # e.g. crc checks out of box
            data = gzip.decompress(data)
        return pickle.loads(data)

    def __str__(self):
        return f"SqlitedictCache <{self.db.filename} | " \
               f"compressed: {self.compressed} | " \
               f"{len(self.db)} records>"

    def __getitem__(self, fingerprint: str):
        return self.db[fingerprint]

    def __setitem__(self, fingerprint: str, value) -> None:
        self.db[fingerprint] = value

    def close(self):
        self.db.close()
