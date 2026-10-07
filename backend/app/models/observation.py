"""Vital sign or laboratory result (≈ FHIR Observation).

One row per measurement. Numeric results carry `value` + `unit`; results
that are not a single number (blood pressure "128/76") carry `value_text`.
`code` is a short stable key (`potassium`, `heart_rate`); production maps it
to LOINC.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class ObservationCategory(StrEnum):
    vital_signs = "vital_signs"
    laboratory = "laboratory"


class ObservationInterpretation(StrEnum):
    normal = "normal"
    low = "low"
    high = "high"
    critical_low = "critical_low"
    critical_high = "critical_high"


class Observation(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "observation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    category: ObservationCategory = Field(sa_type=String(16))  # type: ignore
    code: str = Field(min_length=1, max_length=64, index=True)
    display: str = Field(min_length=1, max_length=128)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=32)
    value_text: str | None = Field(default=None, max_length=64)
    interpretation: ObservationInterpretation = Field(
        default=ObservationInterpretation.normal,
        sa_type=String(16),  # type: ignore
    )
    effective_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class ObservationPublic(SQLModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    category: ObservationCategory
    code: str
    display: str
    value: float | None
    unit: str | None
    value_text: str | None
    interpretation: ObservationInterpretation
    effective_at: datetime
