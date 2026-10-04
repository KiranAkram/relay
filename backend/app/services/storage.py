"""Object storage for recordings behind a small interface.

`LocalDirStorage` writes under a directory on the machine running the backend
(`STORAGE_PROVIDER=local`). An S3/MinIO implementation with the same two
methods arrives with the AWS move; handovers only ever store the key.
"""

import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import Settings


class StorageError(Exception):
    pass


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


class LocalDirStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not key or path == self._root or not path.is_relative_to(self._root):
            raise StorageError(f"invalid storage key {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:  # noqa: ARG002
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise StorageError(f"no object at {key!r}") from None


def audio_key(handover_id: uuid.UUID, filename: str) -> str:
    suffix = Path(filename).suffix.lower() or ".bin"
    return f"handovers/{handover_id}/audio{suffix}"


def get_storage(settings: Settings) -> Storage:
    return LocalDirStorage(Path(settings.STORAGE_LOCAL_DIR))
