"""Speech-to-text behind a small interface.

`OpenAITranscriber` is the only code that touches the audio API.
`FakeTranscriber` returns the demo transcript so everything downstream runs
without a key (`STT_PROVIDER=fake`, the CI default).
"""

from collections.abc import Sequence
from typing import Protocol

from openai import OpenAI

from app.core.config import Settings

# What gpt-transcribe accepts (OpenAI speech-to-text guide).
AUDIO_SUFFIXES = frozenset({".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"})
MAX_AUDIO_BYTES = 25 * 1024 * 1024

CONTEXT_PROMPT = "Spoken physician shift handover on a cardiology coronary care unit."
# Literal terms the model should expect; census surnames are added per call.
WARD_VOCABULARY: tuple[str, ...] = (
    "CCU",
    "I-PASS",
    "stable",
    "watcher",
    "unstable",
    "NSTEMI",
    "STEMI",
    "PCI",
    "TAVI",
    "AF",
    "APTT",
    "BNP",
    "troponin",
    "echo",
    "metoprolol",
    "bisoprolol",
    "amiodarone",
    "heparin",
    "furosemide",
    "vancomycin",
    "pacemaker",
    "endocarditis",
    "cardiomyopathy",
)

# Mirrors FakeExtractor's demo card so fake STT + fake extraction stay coherent.
DEMO_TRANSCRIPT = (
    "Bed 7, he's a watcher. Fast AF overnight, rate now settling on metoprolol. "
    "Bed 7 needs metoprolol by 8:30; if he goes above 120 give another 25 and "
    "call me. Mr Khan is fine, echo should be back this afternoon."
)


class TranscriptionError(Exception):
    pass


class Transcriber(Protocol):
    def transcribe(
        self, audio: bytes, filename: str, hints: Sequence[str] = ()
    ) -> str: ...


class FakeTranscriber:
    def __init__(self, transcript: str = DEMO_TRANSCRIPT) -> None:
        self._transcript = transcript

    def transcribe(
        self,
        audio: bytes,  # noqa: ARG002
        filename: str,  # noqa: ARG002
        hints: Sequence[str] = (),  # noqa: ARG002
    ) -> str:
        return self._transcript


class OpenAITranscriber:
    def __init__(
        self, *, api_key: str, model: str, client: OpenAI | None = None
    ) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def transcribe(self, audio: bytes, filename: str, hints: Sequence[str] = ()) -> str:
        if not audio:
            raise TranscriptionError("audio is empty")
        if len(audio) > MAX_AUDIO_BYTES:
            raise TranscriptionError("audio is larger than 25 MB")
        response = self._client.audio.transcriptions.create(
            model=self._model,
            file=(filename, audio),
            languages=["en"],
            prompt=CONTEXT_PROMPT,
            keywords=list(dict.fromkeys([*WARD_VOCABULARY, *hints])),
            response_format="json",
        )
        text = response.text.strip()
        if not text:
            raise TranscriptionError("transcription came back empty")
        return text


def get_transcriber(settings: Settings) -> Transcriber:
    if settings.STT_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when STT_PROVIDER=openai")
        return OpenAITranscriber(
            api_key=settings.OPENAI_API_KEY, model=settings.STT_MODEL
        )
    return FakeTranscriber()
