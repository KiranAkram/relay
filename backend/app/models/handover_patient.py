"""One I-PASS card per patient mentioned in a handover.

Rows are drafts produced by the extraction pipeline and edited by the outgoing
doctor on the review screen. Action items are not stored here; they become
`task` rows when the handover is confirmed. `patient_id` stays NULL until the
mention is matched to the census (by the matcher or by the doctor).
"""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.handover import Handover


class MatchStatus(StrEnum):
    matched = "matched"  # matcher found exactly one census patient
    ambiguous = "ambiguous"  # several candidates; doctor must choose
    unmatched = "unmatched"  # no candidate found
    doctor_resolved = "doctor_resolved"  # doctor picked/overrode on review


# I-PASS "I": illness severity as stated by the doctor, never inferred.
class IllnessSeverity(StrEnum):
    stable = "stable"
    watcher = "watcher"
    unstable = "unstable"
    unspecified = "unspecified"


class HandoverPatient(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "handover_patient"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    handover_id: uuid.UUID = Field(
        foreign_key="handover.id", nullable=False, index=True, ondelete="CASCADE"
    )
    patient_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="patient.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    # Position of this card in the recording
    order_index: int = 0

    # Patient matching
    mention_verbatim: str = Field(max_length=255)  # "Bed 7", "Mr. Khan"
    match_status: MatchStatus = Field(sa_type=String(32))  # type: ignore
    # [{"patient_id": "...", "reason": "bed exact", "score": 1.0}, ...]
    match_candidates: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSONB)

    # I-PASS content
    illness_severity: IllnessSeverity = Field(
        default=IllnessSeverity.unspecified,
        sa_type=String(16),  # type: ignore
    )
    severity_evidence: str | None = Field(default=None, sa_type=Text)
    patient_summary: str | None = Field(default=None, sa_type=Text)
    situation_awareness: str | None = Field(default=None, sa_type=Text)
    # [{"condition": "K+ < 3.5", "action": "replace", "verbatim": "..."}]
    contingencies: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSONB)
    # [{"description": "troponin trend", "expected_by": "...", "verbatim": "..."}]
    pending_results: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSONB)
    transcript_excerpt: str | None = Field(default=None, sa_type=Text)

    # True once the doctor changed anything on the review screen
    edited_by_doctor: bool = False

    handover: "Handover" = Relationship(back_populates="patients")
