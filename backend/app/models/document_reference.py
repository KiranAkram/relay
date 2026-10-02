"""Pointer to a stored artifact (≈ FHIR DocumentReference).

The pipeline writes handover-level rows (`patient_id` NULL) for the audio,
transcript and extraction JSON. On confirm, one row per matched patient is
added for the audio and transcript so each patient record carries its own
reference, with author and timestamp.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlmodel import Field, Relationship, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.handover import Handover


class DocumentType(StrEnum):
    audio = "audio"
    transcript = "transcript"
    extraction_json = "extraction_json"


class DocumentReference(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "document_reference"

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
    type: DocumentType = Field(sa_type=String(32))  # type: ignore

    # Object storage key; the storage backend turns it into a URL when needed.
    storage_key: str = Field(max_length=512)
    content_type: str = Field(max_length=128)
    size_bytes: int | None = None
    sha256: str | None = Field(default=None, max_length=64)

    author_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="RESTRICT"
    )
    authored_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore

    handover: "Handover" = Relationship(back_populates="documents")
