from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import OpenAI

from app.core.config import settings
from app.services.stt import (
    DEMO_TRANSCRIPT,
    MAX_AUDIO_BYTES,
    FakeTranscriber,
    OpenAITranscriber,
    TranscriptionError,
    get_transcriber,
)


class _StubClient:
    """Records the kwargs of one `audio.transcriptions.create` call."""

    def __init__(self, text: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._create)
        )
        self._text = text

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._text)


def _openai_transcriber(client: _StubClient) -> OpenAITranscriber:
    return OpenAITranscriber(
        api_key="test", model="test-stt", client=cast(OpenAI, client)
    )


def test_fake_transcriber_returns_demo_transcript() -> None:
    assert FakeTranscriber().transcribe(b"\0", "x.m4a") == DEMO_TRANSCRIPT


def test_get_transcriber_picks_provider() -> None:
    fake = settings.model_copy(update={"STT_PROVIDER": "fake"})
    assert isinstance(get_transcriber(fake), FakeTranscriber)
    real = settings.model_copy(update={"STT_PROVIDER": "openai", "OPENAI_API_KEY": "k"})
    assert isinstance(get_transcriber(real), OpenAITranscriber)
    no_key = settings.model_copy(
        update={"STT_PROVIDER": "openai", "OPENAI_API_KEY": None}
    )
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_transcriber(no_key)


def test_openai_transcriber_sends_file_vocabulary_and_hints() -> None:
    client = _StubClient("  Bed 7 needs metoprolol by 8:30.  ")
    text = _openai_transcriber(client).transcribe(b"audio", "handover.m4a", ["Khan"])

    assert text == "Bed 7 needs metoprolol by 8:30."
    (call,) = client.calls
    assert call["model"] == "test-stt"
    assert call["file"] == ("handover.m4a", b"audio")
    assert call["languages"] == ["en"]
    assert call["response_format"] == "json"
    assert "metoprolol" in call["keywords"]
    assert call["keywords"][-1] == "Khan"
    assert len(call["keywords"]) == len(set(call["keywords"]))


def test_openai_transcriber_rejects_empty_audio_without_calling() -> None:
    client = _StubClient("text")
    with pytest.raises(TranscriptionError, match="empty"):
        _openai_transcriber(client).transcribe(b"", "x.wav")
    assert client.calls == []


def test_openai_transcriber_rejects_oversized_audio() -> None:
    client = _StubClient("text")
    with pytest.raises(TranscriptionError, match="25 MB"):
        _openai_transcriber(client).transcribe(b"\0" * (MAX_AUDIO_BYTES + 1), "x.wav")
    assert client.calls == []


def test_openai_transcriber_rejects_blank_transcript() -> None:
    client = _StubClient("   ")
    with pytest.raises(TranscriptionError, match="empty"):
        _openai_transcriber(client).transcribe(b"audio", "x.wav")
