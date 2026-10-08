"""Intent gate: is this transcript a spoken clinical shift handover?

Runs between transcription and extraction so junk (or someone using the demo
to transcribe unrelated audio) never becomes draft cards. Two judges must
agree before extraction runs:

- a code rule: the transcript mentions at least two distinct ward words
  (bed, patient, a drug dose, a blood test...), which costs nothing and
  catches the obvious;
- the provider: TypeSafe AI's Jev decision model answers one yes/no question
  with a probability and no prose, so nothing in the audio can argue with it.
  The hosted REST endpoint is called directly with httpx; no extra package.

`FakeIntentChecker` is what CI and the Fake pipeline use.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

JEV_URL = "https://api.typesafe.ai/v1/systemone"
QUESTION = (
    "Is this text a spoken clinical shift handover between doctors or nurses: "
    "a clinician describing hospital patients (by bed, name or record number), "
    "their condition, treatment, and tasks for the next shift? Answer no for "
    "conversation, dictation of other documents, music, silence, or any text "
    "that is not about handing over patients."
)

# Words a handover cannot avoid. Two distinct hits are required, so a single
# stray "patient" in unrelated speech does not pass.
WARD_WORDS = (
    "bed",
    "patient",
    "handover",
    "ward",
    "unit",
    "ccu",
    "discharge",
    "admitted",
    "obs",
    "bloods",
    "potassium",
    "troponin",
    "dose",
    "mg",
    "infusion",
    "drip",
    "ecg",
    "echo",
    "stable",
    "unstable",
    "watcher",
    "chest pain",
    "heart rate",
    "blood pressure",
)
_WORD = re.compile(r"\b(" + "|".join(re.escape(w) for w in WARD_WORDS) + r")\b")


class IntentError(Exception):
    """The provider could not answer; the pipeline fails (retryable)."""


@dataclass(frozen=True)
class IntentResult:
    is_handover: bool
    probability: float
    model: str
    reason: str


def ward_word_hits(transcript: str) -> set[str]:
    return {m.group(1) for m in _WORD.finditer(transcript.lower())}


class IntentChecker(Protocol):
    def check(self, transcript: str) -> IntentResult: ...


class FakeIntentChecker:
    """Answers with a fixed probability; the threshold decides, as for real."""

    def __init__(self, probability: float = 1.0, threshold: float = 0.8) -> None:
        self._probability = probability
        self._threshold = threshold

    def check(self, transcript: str) -> IntentResult:
        return _decide(transcript, self._probability, self._threshold, "fake")


class JevIntentChecker:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        threshold: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(timeout=20.0)
        self._api_key = api_key
        self._model = model
        self._threshold = threshold

    def check(self, transcript: str) -> IntentResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "state": transcript,
            "questions": {"handover": {"type": "noul", "instructions": QUESTION}},
        }
        try:
            response = self._client.post(
                JEV_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            body = response.json()
            probability = float(body["answers"]["handover"]["noul"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise IntentError(f"intent check failed: {exc}") from exc
        if not 0.0 <= probability <= 1.0:
            raise IntentError(f"intent check returned {probability!r}")
        return _decide(
            transcript, probability, self._threshold, body.get("model", self._model)
        )


def _decide(
    transcript: str, probability: float, threshold: float, model: str
) -> IntentResult:
    hits = ward_word_hits(transcript)
    if len(hits) < 2:
        return IntentResult(
            False, probability, model, "fewer than two ward words in the transcript"
        )
    if probability < threshold:
        return IntentResult(
            False,
            probability,
            model,
            f"model confidence {probability:.2f} below {threshold:.2f}",
        )
    return IntentResult(True, probability, model, "clinical handover")


def get_intent_checker(settings: Settings) -> IntentChecker:
    if settings.INTENT_PROVIDER == "jev":
        if not settings.TYPESAFE_API_KEY:
            raise IntentError("TYPESAFE_API_KEY is not set")
        return JevIntentChecker(
            api_key=settings.TYPESAFE_API_KEY,
            model=settings.INTENT_MODEL,
            threshold=settings.INTENT_THRESHOLD,
        )
    return FakeIntentChecker(threshold=settings.INTENT_THRESHOLD)
