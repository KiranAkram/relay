"""Active problem on a patient's record (≈ FHIR Condition).

Clinical context for the handover: what the patient is being treated for.
Written by the seed and by admins; the handover pipeline only reads it.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class ConditionStatus(StrEnum):
    active = "active"
    resolved = "resolved"


class Condition(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "condition"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    # Free text for the prototype; production maps to SNOMED CT codes.
    text: str = Field(min_length=1, max_length=256)
    status: ConditionStatus = Field(
        default=ConditionStatus.active,
        sa_type=String(16),  # type: ignore
    )
    recorded_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore


class ConditionPublic(SQLModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    text: str
    status: ConditionStatus
    recorded_at: datetime
