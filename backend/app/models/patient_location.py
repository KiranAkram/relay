"""Bed history for a stay (≈ FHIR Encounter.location).

One row per bed the patient has occupied; the open row (`end_at` NULL) is
the current bed and mirrors `patient.bed`. Lets matching recognise a bed the
patient was moved out of instead of treating it as unknown.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class PatientLocation(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "patient_location"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    bed: str = Field(min_length=1, max_length=32, index=True)
    unit: str | None = Field(default=None, max_length=64)
    start_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore
    end_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class PatientLocationPublic(SQLModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    bed: str
    unit: str | None
    start_at: datetime
    end_at: datetime | None
