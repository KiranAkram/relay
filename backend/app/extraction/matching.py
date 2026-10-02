"""Spoken patient reference → census patient.

Every result carries its candidates so the review screen can show why. A
mention is `matched` only when exactly one patient is hit and every spoken cue
(mrn, bed, name) agrees on it; anything else is left to the doctor.
"""

import re
import uuid
from collections.abc import Sequence
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.extraction.schema import PatientMention
from app.models import MatchStatus, Patient

NAME_THRESHOLD = 0.85

_HONORIFICS = frozenset(
    {"mr", "mrs", "ms", "miss", "mister", "mx", "dr", "doctor", "sir", "madam"}
)
# "CCU-7", "Bed 7", "7" all reduce to "7"; "7A" stays "7a".
_BED_FROM_FIRST_DIGIT = re.compile(r"^[a-z]*(\d.*)$")


class MatchCandidate(BaseModel):
    patient_id: uuid.UUID
    reason: str  # "mrn exact", "bed exact", "name fuzzy"
    score: float


class MatchResult(BaseModel):
    status: MatchStatus
    patient_id: uuid.UUID | None = None
    candidates: list[MatchCandidate] = Field(default_factory=list)


def match_mention(mention: PatientMention, census: Sequence[Patient]) -> MatchResult:
    """`census` is the caller's active patient list (already filtered)."""
    cue_hits: list[dict[uuid.UUID, MatchCandidate]] = []

    if mrn_key := _mrn_key(mention.mrn):
        cue_hits.append(
            {
                p.id: MatchCandidate(patient_id=p.id, reason="mrn exact", score=1.0)
                for p in census
                if _mrn_key(p.mrn) == mrn_key
            }
        )
    if bed_key := _bed_key(mention.bed):
        cue_hits.append(
            {
                p.id: MatchCandidate(patient_id=p.id, reason="bed exact", score=1.0)
                for p in census
                if _bed_key(p.bed) == bed_key
            }
        )
    if name_key := _name_key(mention.name):
        hits: dict[uuid.UUID, MatchCandidate] = {}
        for p in census:
            score = _name_score(name_key, p)
            if score >= NAME_THRESHOLD:
                hits[p.id] = MatchCandidate(
                    patient_id=p.id, reason="name fuzzy", score=score
                )
        cue_hits.append(hits)

    merged: dict[uuid.UUID, MatchCandidate] = {}
    for hits in cue_hits:
        for patient_id, candidate in hits.items():
            if (seen := merged.get(patient_id)) is not None:
                candidate = MatchCandidate(
                    patient_id=patient_id,
                    reason=f"{seen.reason}, {candidate.reason}",
                    score=max(seen.score, candidate.score),
                )
            merged[patient_id] = candidate
    candidates = sorted(merged.values(), key=lambda c: c.score, reverse=True)

    if not candidates:
        return MatchResult(status=MatchStatus.unmatched)
    if len(candidates) == 1 and all(len(hits) == 1 for hits in cue_hits):
        return MatchResult(
            status=MatchStatus.matched,
            patient_id=candidates[0].patient_id,
            candidates=candidates,
        )
    return MatchResult(status=MatchStatus.ambiguous, candidates=candidates)


def _mrn_key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _bed_key(value: str | None) -> str:
    key = re.sub(r"[^a-z0-9]", "", (value or "").casefold())
    match = _BED_FROM_FIRST_DIGIT.match(key)
    return match.group(1) if match else key.removeprefix("bed")


def _name_key(value: str | None) -> str:
    words = re.sub(r"[^a-z\s]", "", (value or "").casefold()).split()
    return " ".join(w for w in words if w not in _HONORIFICS)


def _name_score(name_key: str, patient: Patient) -> float:
    family = patient.family_name.casefold()
    given = patient.given_name.casefold()
    return max(
        SequenceMatcher(None, name_key, candidate).ratio()
        for candidate in (family, given, f"{given} {family}")
    )
