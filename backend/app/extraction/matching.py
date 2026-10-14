"""Spoken patient reference → census patient.

Every result carries its candidates so the review screen can show why.

The bed decides (owner's decision, 12 Oct 2026). A spoken bed that holds a
census patient is matched to that patient whatever name was said; if the
spoken name is not that patient's name, the candidate carries a `name_note`
so the review card says so and the doctor can change the patient. Only when
no bed was said, or the bed holds nobody, does the code look further: an MRN
read out, then the name, which must be exactly one patient's name (titles
ignored). No such patient is `unmatched`, several are `ambiguous`; the doctor
checks the name and bed and chooses.
"""

import re
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.extraction.schema import PatientMention
from app.models import MatchStatus, Patient

# Words that are not part of a name: titles, Urdu honorifics, "the Sheikh".
_NOT_NAME = frozenset(
    {"mr", "mrs", "ms", "miss", "mister", "mx", "dr", "doctor", "sir", "madam"}
    | {"sahab", "sahib", "ji"}  # Urdu, after the name: "Abbas sahab"
    | {"the"}
)
# "CCU-7", "Bed 7", "7" all reduce to "7"; "7A" stays "7a".
_BED_FROM_FIRST_DIGIT = re.compile(r"^[a-z]*(\d.*)$")


class MatchCandidate(BaseModel):
    patient_id: uuid.UUID
    reason: str  # "bed exact", "mrn exact", "name exact"
    score: float
    # Set when the bed decided but the spoken name is not this patient's.
    name_note: str | None = None


class MatchResult(BaseModel):
    status: MatchStatus
    patient_id: uuid.UUID | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)


def match_mention(mention: PatientMention, census: Sequence[Patient]) -> MatchResult:
    """`census` is the caller's active patient list (already filtered)."""
    if bed_key := _bed_key(mention.bed):
        in_bed = [p for p in census if _bed_key(p.bed) == bed_key]
        if len(in_bed) == 1:
            return _matched(in_bed[0], "bed exact", _name_note(mention, in_bed[0]))

    if mrn_key := _mrn_key(mention.mrn):
        by_mrn = [p for p in census if _mrn_key(p.mrn) == mrn_key]
        if len(by_mrn) == 1:
            return _matched(by_mrn[0], "mrn exact")

    words = _name_words(mention.name)
    if not words:
        return MatchResult(status=MatchStatus.unmatched)
    by_name = [p for p in census if words <= _patient_words(p)]
    if len(by_name) == 1:
        return _matched(by_name[0], "name exact")
    candidates = [
        MatchCandidate(patient_id=p.id, reason="name exact", score=1.0) for p in by_name
    ]
    status = MatchStatus.ambiguous if candidates else MatchStatus.unmatched
    return MatchResult(status=status, candidates=candidates)


def _matched(patient: Patient, reason: str, note: str | None = None) -> MatchResult:
    return MatchResult(
        status=MatchStatus.matched,
        patient_id=patient.id,
        candidates=[
            MatchCandidate(
                patient_id=patient.id, reason=reason, score=1.0, name_note=note
            )
        ],
    )


def _name_note(mention: PatientMention, patient: Patient) -> str | None:
    words = _name_words(mention.name)
    if not words or words <= _patient_words(patient):
        return None
    return f"Transcript says “{mention.name}”"


def _mrn_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _bed_key(value: str | None) -> str:
    key = re.sub(r"[^a-z0-9]", "", (value or "").casefold())
    match = _BED_FROM_FIRST_DIGIT.match(key)
    return match.group(1) if match else key.removeprefix("bed")


def _name_words(value: str | None) -> set[str]:
    """Spoken name words, titles dropped: "Mrs Ahmed, Farida Ahmed" -> {ahmed, farida}."""
    words = re.sub(r"[^a-z\s]", " ", (value or "").casefold()).split()
    return {w for w in words if w not in _NOT_NAME}


def _patient_words(patient: Patient) -> set[str]:
    return _name_words(f"{patient.given_name} {patient.family_name}")
