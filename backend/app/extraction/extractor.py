"""LLM extraction behind a small interface.

`OpenAIExtractor` is the only code that touches the OpenAI client.
`FakeExtractor` returns a canned handover so every downstream step runs
without a key (`LLM_PROVIDER=fake`, the CI default).
"""

from typing import Protocol

from openai import OpenAI

from app.core.config import Settings
from app.extraction.prompt import get_prompt, user_message
from app.extraction.schema import (
    ActionItem,
    Contingency,
    HandoverExtraction,
    PatientCard,
    PatientMention,
    PendingResult,
    SpokenTime,
)
from app.models import DueKind, IllnessSeverity, TaskPriority


class ExtractionError(Exception):
    pass


class Extractor(Protocol):
    def extract(self, transcript: str) -> HandoverExtraction: ...


# What the demo transcript ("Bed 7 needs metoprolol by 8:30") should come back
# as. "Mr Khan" has no bed so the matcher leaves it ambiguous (two Khans).
DEMO_EXTRACTION = HandoverExtraction(
    patients=[
        PatientCard(
            mention=PatientMention(bed="7", verbatim="Bed 7"),
            illness_severity=IllnessSeverity.watcher,
            severity_evidence="he's a watcher",
            patient_summary="Fast AF overnight, rate now settling on metoprolol.",
            situation_awareness="Rate may climb again if the next dose is late.",
            contingencies=[
                Contingency(
                    condition="heart rate above 120",
                    action="give an extra 25 mg metoprolol and call me",
                    verbatim="if he goes above 120 give another 25 and call me",
                )
            ],
            action_items=[
                ActionItem(
                    description="Give metoprolol",
                    due=SpokenTime(
                        kind=DueKind.clock, clock_time="08:30", phrase="by 8:30"
                    ),
                    priority=TaskPriority.routine,
                    verbatim="Bed 7 needs metoprolol by 8:30",
                )
            ],
            transcript_excerpt=(
                "Bed 7, he's a watcher. Fast AF overnight, rate now settling on "
                "metoprolol. Bed 7 needs metoprolol by 8:30; if he goes above "
                "120 give another 25 and call me."
            ),
        ),
        PatientCard(
            mention=PatientMention(name="Mr Khan", verbatim="Mr Khan"),
            patient_summary="Stable, awaiting echo.",
            pending_results=[
                PendingResult(
                    description="echo",
                    expected_by="this afternoon",
                    verbatim="echo should be back this afternoon",
                )
            ],
            transcript_excerpt=("Mr Khan is fine, echo should be back this afternoon."),
        ),
    ]
)


class FakeExtractor:
    def __init__(self, extraction: HandoverExtraction = DEMO_EXTRACTION) -> None:
        self._extraction = extraction

    def extract(self, transcript: str) -> HandoverExtraction:  # noqa: ARG002
        return self._extraction.model_copy(deep=True)


class OpenAIExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_version: str,
        client: OpenAI | None = None,
    ) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._instructions = get_prompt(prompt_version)

    def extract(self, transcript: str) -> HandoverExtraction:
        if not transcript.strip():
            raise ExtractionError("transcript is empty")
        response = self._client.responses.parse(
            model=self._model,
            instructions=self._instructions,
            input=user_message(transcript),
            text_format=HandoverExtraction,
            # Reasoning models reject `temperature`; low effort is enough for
            # copying structure out of a transcript.
            reasoning={"effort": "low"},
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ExtractionError(_refusal_text(response) or "no structured output")
        return parsed


def _refusal_text(response: object) -> str | None:
    for item in getattr(response, "output", []):
        for part in getattr(item, "content", []):
            if getattr(part, "type", None) == "refusal":
                refusal = getattr(part, "refusal", None)
                return str(refusal) if refusal else None
    return None


def get_extractor(settings: Settings) -> Extractor:
    if settings.LLM_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIExtractor(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            prompt_version=settings.EXTRACTION_PROMPT_VERSION,
        )
    return FakeExtractor()
