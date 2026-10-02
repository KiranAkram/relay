"""Shape of what the LLM extractor returns for one handover transcript.

The LLM never does date math or identity matching. Due times come back as
spoken components (`SpokenTime`, resolved by `timing.py`) and patients as the
reference as spoken (`PatientMention`, resolved by `matching.py`). `verbatim`
fields keep the source wording for the review screen.
"""

import re

from pydantic import BaseModel, Field, field_validator

from app.models import DueKind, IllnessSeverity, TaskPriority

_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


class PatientMention(BaseModel):
    bed: str | None = None  # "7" — unit prefix optional
    name: str | None = None  # "Mr. Khan", "Zubaida Khan"
    mrn: str | None = None
    verbatim: str


class SpokenTime(BaseModel):
    kind: DueKind = DueKind.unspecified
    # "HH:MM". 24h when am/pm was stated ("8:30 pm" → "20:30"), otherwise the
    # hour as spoken ("8:30" → "08:30") so timing.py can try both readings.
    clock_time: str | None = None
    meridiem_stated: bool = False
    relative_minutes: int | None = None
    phrase: str | None = None  # "by 8:30", "in an hour"

    @field_validator("clock_time")
    @classmethod
    def _normalise_clock_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        match = _CLOCK_RE.match(value.strip())
        if match is None:
            raise ValueError("clock_time must be HH:MM")
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError("clock_time out of range")
        return f"{hour:02d}:{minute:02d}"


class ActionItem(BaseModel):
    description: str
    due: SpokenTime = Field(default_factory=SpokenTime)
    priority: TaskPriority = TaskPriority.routine
    verbatim: str | None = None


class Contingency(BaseModel):
    condition: str  # "K+ < 3.5"
    action: str  # "replace"
    verbatim: str | None = None


class PendingResult(BaseModel):
    description: str  # "troponin trend"
    expected_by: str | None = None  # as spoken; not resolved to a timestamp
    verbatim: str | None = None


class PatientCard(BaseModel):
    mention: PatientMention
    # Only what the doctor said; `unspecified` unless stated.
    illness_severity: IllnessSeverity = IllnessSeverity.unspecified
    severity_evidence: str | None = None
    patient_summary: str | None = None
    situation_awareness: str | None = None
    contingencies: list[Contingency] = Field(default_factory=list)
    pending_results: list[PendingResult] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    transcript_excerpt: str | None = None


class HandoverExtraction(BaseModel):
    patients: list[PatientCard] = Field(default_factory=list)
