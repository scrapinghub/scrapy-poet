import abc
import os
import pickle
from pathlib import Path
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
        self.directory = Path(directory)

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
            storage_path = self._get_directory_path(fingerprint)
            storage_path.mkdir(parents=True, exist_ok=True)
            storage = SerializedDataFileStorage(storage_path)
            storage.write(value)

    def write_exception(self, fingerprint: str, exception: Exception) -> None:
        exception_path = self._get_exception_file_path(fingerprint)
        exception_path.parent.mkdir(parents=True, exist_ok=True)
        with exception_path.open("wb") as file:
            pickle.dump(exception, file)

    def _get_directory_path(self, fingerprint: str) -> Path:
        return self.directory / fingerprint

    def _get_exception_file_path(self, fingerprint: str) -> Path:
        """Save exception inside self.directory, so that `storage.read()` can read it correctly"""
        return self._get_directory_path(fingerprint) / "error"

    # TODO: Add option for compressed cache
