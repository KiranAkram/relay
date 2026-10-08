"""Intent gate: ward-word rule, Jev request/response handling, settings wiring."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services.intent import (
    JEV_URL,
    FakeIntentChecker,
    IntentError,
    JevIntentChecker,
    get_intent_checker,
    ward_word_hits,
)
from app.services.stt import DEMO_TRANSCRIPT

CHAT = "So anyway we went to the market and then it rained all afternoon, lovely."


def test_fake_checker_accepts_the_demo_transcript_and_refuses_chat() -> None:
    checker = FakeIntentChecker()
    assert checker.check(DEMO_TRANSCRIPT).is_handover is True
    refused = checker.check(CHAT)
    assert refused.is_handover is False
    assert "ward words" in refused.reason


def test_ward_words_need_two_distinct_hits() -> None:
    assert ward_word_hits("the patient, the patient, the patient") == {"patient"}
    assert {"bed", "mg"} <= ward_word_hits("Bed 3 needs 40 mg now")


def _jev(handler: httpx.MockTransport, threshold: float = 0.8) -> JevIntentChecker:
    return JevIntentChecker(
        api_key="test-key",
        model="jev-latest",
        threshold=threshold,
        client=httpx.Client(transport=handler),
    )


def test_jev_checker_sends_one_noul_question_and_reads_the_probability() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "model": "jev-2026-09",
                "answers": {"handover": {"type": "noul", "noul": 0.93}},
                "usage": {"input_tokens": 120, "output_tokens": 0},
            },
        )

    result = _jev(httpx.MockTransport(handler)).check(DEMO_TRANSCRIPT)
    assert result.is_handover is True
    assert result.probability == pytest.approx(0.93)
    assert result.model == "jev-2026-09"

    (request,) = seen
    assert str(request.url) == JEV_URL
    assert request.headers["authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["state"] == DEMO_TRANSCRIPT
    assert body["questions"]["handover"]["type"] == "noul"


def test_jev_below_threshold_is_refused_with_the_confidence() -> None:
    handler = httpx.MockTransport(
        lambda _r: httpx.Response(
            200, json={"answers": {"handover": {"type": "noul", "noul": 0.41}}}
        )
    )
    result = _jev(handler).check(DEMO_TRANSCRIPT)
    assert result.is_handover is False
    assert "0.41 below 0.80" in result.reason


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(200, json={"answers": {}}),
        httpx.Response(200, json={"answers": {"handover": {"noul": "high"}}}),
        httpx.Response(200, json={"answers": {"handover": {"noul": 1.7}}}),
    ],
)
def test_jev_errors_raise_so_the_pipeline_fails_instead_of_guessing(
    response: httpx.Response,
) -> None:
    with pytest.raises(IntentError):
        _jev(httpx.MockTransport(lambda _r: response)).check(DEMO_TRANSCRIPT)


def test_settings_pick_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(get_intent_checker(settings), FakeIntentChecker)
    monkeypatch.setattr(settings, "INTENT_PROVIDER", "jev")
    monkeypatch.setattr(settings, "TYPESAFE_API_KEY", None)
    with pytest.raises(IntentError):
        get_intent_checker(settings)
    monkeypatch.setattr(settings, "TYPESAFE_API_KEY", "k")
    assert isinstance(get_intent_checker(settings), JevIntentChecker)
