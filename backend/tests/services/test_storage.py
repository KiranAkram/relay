import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.storage import (
    LocalDirStorage,
    StorageError,
    audio_key,
    get_storage,
)


def test_put_then_get_roundtrip_in_nested_key(tmp_path: Path) -> None:
    storage = LocalDirStorage(tmp_path)
    storage.put("handovers/abc/audio.m4a", b"audio-bytes", "audio/mp4")
    assert storage.get("handovers/abc/audio.m4a") == b"audio-bytes"
    assert (tmp_path / "handovers" / "abc" / "audio.m4a").is_file()


def test_put_overwrites_existing_object(tmp_path: Path) -> None:
    storage = LocalDirStorage(tmp_path)
    storage.put("k", b"one", "application/octet-stream")
    storage.put("k", b"two", "application/octet-stream")
    assert storage.get("k") == b"two"


def test_get_missing_key_raises(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="no object"):
        LocalDirStorage(tmp_path).get("handovers/missing/audio.m4a")


@pytest.mark.parametrize("key", ["", "../escape.txt", "/etc/passwd", "a/../../b"])
def test_keys_outside_root_are_rejected(tmp_path: Path, key: str) -> None:
    storage = LocalDirStorage(tmp_path)
    with pytest.raises(StorageError, match="invalid storage key"):
        storage.put(key, b"x", "text/plain")


def test_audio_key_uses_handover_id_and_lowercased_suffix() -> None:
    handover_id = uuid.uuid4()
    assert (
        audio_key(handover_id, "Recording.M4A") == f"handovers/{handover_id}/audio.m4a"
    )
    assert audio_key(handover_id, "noext") == f"handovers/{handover_id}/audio.bin"


def test_get_storage_uses_configured_dir() -> None:
    storage = get_storage(settings.model_copy(update={"STORAGE_LOCAL_DIR": "some/dir"}))
    assert isinstance(storage, LocalDirStorage)
