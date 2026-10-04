"""One recorded handover session (≈ FHIR Composition).

A handover is created when the outgoing doctor uploads a recording and moves
through the pipeline states below. Until `confirmed`, everything attached to it
is a draft; nothing is written to patient records before that.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin
from app.models.handover_patient import HandoverPatientPublic

if TYPE_CHECKING:
    from app.models.document_reference import DocumentReference
    from app.models.handover_patient import HandoverPatient


class HandoverStatus(StrEnum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    extracting = "extracting"
    matching = "matching"
    awaiting_review = "awaiting_review"
    confirmed = "confirmed"
    failed = "failed"
    discarded = "discarded"


class Handover(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Outgoing doctor. RESTRICT: a handover must outlive its author's account.
    author_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    status: HandoverStatus = Field(
        default=HandoverStatus.uploaded,
        sa_type=String(32),  # type: ignore
        index=True,
    )
    # Client-side timestamp of the recording; anchor for "in an hour" → absolute time.
    recorded_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    shift_label: str | None = Field(default=None, max_length=64)

    # Audio (object storage key, not a URL — the storage backend resolves it)
    audio_key: str = Field(max_length=512)
    audio_content_type: str = Field(max_length=128)
    audio_duration_s: float | None = None

    # Speech-to-text output
    transcript_text: str | None = Field(default=None, sa_type=Text)
    transcript_provider: str | None = Field(default=None, max_length=64)
    transcript_model: str | None = Field(default=None, max_length=64)

    # LLM extraction output, exactly as returned (immutable; edits go on handover_patient)
    extraction_raw: dict[str, Any] | None = Field(default=None, sa_type=JSONB)
    extraction_model: str | None = Field(default=None, max_length=64)
    extraction_prompt_version: str | None = Field(default=None, max_length=32)

    # Pipeline bookkeeping
    attempts: int = 0
    last_error: str | None = Field(default=None, sa_type=Text)

    confirmed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    confirmed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="RESTRICT"
    )

    patients: list["HandoverPatient"] = Relationship(
        back_populates="handover", cascade_delete=True
    )
    documents: list["DocumentReference"] = Relationship(
        back_populates="handover", cascade_delete=True
    )


# Properties to return via API. No storage key and no raw extraction: the
# doctor reviews the cards, not the LLM output.
class HandoverPublic(SQLModel):
    id: uuid.UUID
    author_id: uuid.UUID
    status: HandoverStatus
    recorded_at: datetime
    shift_label: str | None
    audio_content_type: str
    transcript_text: str | None
    attempts: int
    last_error: str | None
    confirmed_at: datetime | None
    confirmed_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class HandoverDetailPublic(HandoverPublic):
    patients: list[HandoverPatientPublic]


class HandoversPublic(SQLModel):
    data: list[HandoverPublic]
    count: int
