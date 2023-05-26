import abc
import os
import pickle
from typing import Any, Union

from web_poet.serialization.api import SerializedData, SerializedDataFileStorage


class _Cache(abc.ABC):
    @abc.abstractmethod
    def __getitem__(self, fingerprint: str) -> Any:
        pass

    @abc.abstractmethod
    def __setitem__(self, fingerprint: str, value) -> None:
        pass

    def close(self) -> None:  # noqa: B027
        pass


class SerializedDataCache(_Cache):
    """
    Stores dependencies from Providers in a persistent local storage using
    `web_poet.serialization.SerializedDataFileStorage`
    """

    def __init__(self, directory: Union[str, os.PathLike]) -> None:
        self.directory = directory

    def __getitem__(self, fingerprint: str) -> SerializedData:
        storage = SerializedDataFileStorage(self._get_directory_path(fingerprint))
        try:
            serialized_data = storage.read()
        except FileNotFoundError:
            raise KeyError(f"Fingerprint '{fingerprint}' not found in cache")
        return serialized_data

    def __setitem__(
        self, fingerprint: str, value: Union[SerializedData, Exception]
    ) -> None:
        if isinstance(value, Exception):
            self.write_exception(fingerprint, value)
        else:
            storage = SerializedDataFileStorage(self._get_directory_path(fingerprint))
            storage.write(value)

    def write_exception(self, fingerprint: str, exception: Exception) -> None:
        with open(self._get_exception_file_path(fingerprint), "wb") as file:
            pickle.dump(exception, file)

    def _get_directory_path(self, fingerprint: str) -> str:
        return os.path.join(self.directory, fingerprint)

    def _get_exception_file_path(self, fingerprint: str) -> str:
        """Save exception inside self.directory, so that `storage.read()` can read it correctly"""
        return os.path.join(
            self._get_directory_path(fingerprint), f"{fingerprint}.error"
        )

    # TODO: Add option for compressed cache
