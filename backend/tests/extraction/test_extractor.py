from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import OpenAI

from app.core.config import settings
from app.extraction.extractor import (
    DEMO_EXTRACTION,
    ExtractionError,
    FakeExtractor,
    OpenAIExtractor,
    get_extractor,
)
from app.extraction.prompt import get_prompt, user_message
from app.extraction.schema import HandoverExtraction
from app.models import DueKind


class _StubClient:
    """Records the kwargs of one `responses.parse` call and returns a canned response."""

    def __init__(self, response: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(parse=self._parse)
        self._response = response

    def _parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._response


def _openai_extractor(client: _StubClient) -> OpenAIExtractor:
    return OpenAIExtractor(
        api_key="test",
        model="test-model",
        prompt_version="v1",
        client=cast(OpenAI, client),
    )


def test_fake_extractor_returns_demo_handover() -> None:
    extraction = FakeExtractor().extract("anything")
    assert isinstance(extraction, HandoverExtraction)
    bed_7 = extraction.patients[0]
    assert bed_7.mention.bed == "7"
    assert bed_7.action_items[0].due.kind == DueKind.clock
    assert bed_7.action_items[0].due.clock_time == "08:30"


def test_fake_extractor_returns_a_fresh_copy_each_call() -> None:
    extractor = FakeExtractor()
    first = extractor.extract("x")
    first.patients.clear()
    assert len(extractor.extract("x").patients) == len(DEMO_EXTRACTION.patients)


def test_unknown_prompt_version_raises() -> None:
    with pytest.raises(ValueError, match="unknown prompt version"):
        get_prompt("v0")


def test_get_extractor_picks_provider() -> None:
    assert isinstance(
        get_extractor(settings.model_copy(update={"LLM_PROVIDER": "fake"})),
        FakeExtractor,
    )
    openai_settings = settings.model_copy(
        update={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test"}
    )
    assert isinstance(get_extractor(openai_settings), OpenAIExtractor)


def test_get_extractor_openai_without_key_raises() -> None:
    bad = settings.model_copy(update={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": None})
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_extractor(bad)


def test_openai_extractor_sends_prompt_and_parses_schema() -> None:
    client = _StubClient(SimpleNamespace(output_parsed=DEMO_EXTRACTION, output=[]))
    result = _openai_extractor(client).extract("Bed 7 needs metoprolol by 8:30")

    assert result == DEMO_EXTRACTION
    (call,) = client.calls
    assert call["model"] == "test-model"
    assert call["instructions"] == get_prompt("v1")
    assert call["input"] == user_message("Bed 7 needs metoprolol by 8:30")
    assert call["text_format"] is HandoverExtraction
    assert call["reasoning"] == {"effort": "low"}
    assert "temperature" not in call


def test_openai_extractor_surfaces_refusal() -> None:
    refusal = SimpleNamespace(type="refusal", refusal="I can't help with that.")
    message = SimpleNamespace(type="message", content=[refusal])
    client = _StubClient(SimpleNamespace(output_parsed=None, output=[message]))
    with pytest.raises(ExtractionError, match="can't help"):
        _openai_extractor(client).extract("some transcript")


def test_openai_extractor_rejects_empty_transcript() -> None:
    client = _StubClient(SimpleNamespace(output_parsed=None, output=[]))
    with pytest.raises(ExtractionError, match="empty"):
        _openai_extractor(client).extract("   ")
    assert client.calls == []
