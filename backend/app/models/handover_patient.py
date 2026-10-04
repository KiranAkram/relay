"""One I-PASS card per patient mentioned in a handover.

Rows are drafts produced by the extraction pipeline and edited by the outgoing
doctor on the review screen. Draft action items are kept in `action_items`
(JSONB) and become `task` rows only when the handover is confirmed.
`patient_id` stays NULL until the mention is matched to the census (by the
matcher or by the doctor).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin
from app.models.task import DueKind, TaskPriority

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
    # Draft tasks with due times already resolved by extraction/resolve.py:
    # [{"description", "priority", "due_kind", "due_phrase", "due_at",
    #   "needs_review", "review_reason", "verbatim"}]
    action_items: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSONB)
    transcript_excerpt: str | None = Field(default=None, sa_type=Text)

    # True once the doctor changed anything on the review screen
    edited_by_doctor: bool = False

    handover: "Handover" = Relationship(back_populates="patients")


# One entry of `match_candidates`, enriched with census details for the review screen.
class MatchCandidatePublic(SQLModel):
    patient_id: uuid.UUID
    reason: str
    score: float
    family_name: str | None = None
    given_name: str | None = None
    bed: str | None = None
    mrn: str | None = None


# One entry of `action_items` (the dict built by extraction/resolve.py), typed so
# confirm never has to parse free text.
class ActionItemDraft(SQLModel):
    description: str = Field(min_length=1)
    priority: TaskPriority = TaskPriority.routine
    due_kind: DueKind = DueKind.unspecified
    due_phrase: str | None = Field(default=None, max_length=128)
    due_at: datetime | None = None
    needs_review: bool = False
    review_reason: str | None = None
    verbatim: str | None = None


# Properties to return via API
class HandoverPatientPublic(SQLModel):
    id: uuid.UUID
    handover_id: uuid.UUID
    patient_id: uuid.UUID | None
    order_index: int
    mention_verbatim: str
    match_status: MatchStatus
    match_candidates: list[MatchCandidatePublic]
    illness_severity: IllnessSeverity
    severity_evidence: str | None
    patient_summary: str | None
    situation_awareness: str | None
    contingencies: list[dict[str, Any]]
    pending_results: list[dict[str, Any]]
    action_items: list[ActionItemDraft]
    transcript_excerpt: str | None
    edited_by_doctor: bool
    created_at: datetime
    updated_at: datetime


# Properties the doctor may change on the review screen, all optional
class HandoverPatientUpdate(SQLModel):
    patient_id: uuid.UUID | None = None
    illness_severity: IllnessSeverity | None = None
    patient_summary: str | None = None
    situation_awareness: str | None = None
    contingencies: list[dict[str, Any]] | None = None
    pending_results: list[dict[str, Any]] | None = None
    action_items: list[ActionItemDraft] | None = None
