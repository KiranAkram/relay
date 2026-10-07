"""Current medication on a patient's record (≈ FHIR MedicationStatement).

Dose, route and frequency are kept as the clinician writes them; production
maps to coded drugs and structured dosage.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class MedicationStatus(StrEnum):
    active = "active"
    on_hold = "on_hold"
    stopped = "stopped"


class MedicationStatement(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "medication_statement"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    medication: str = Field(min_length=1, max_length=128)
    dose: str = Field(max_length=64)
    route: str = Field(max_length=32)
    frequency: str = Field(max_length=64)
    status: MedicationStatus = Field(
        default=MedicationStatus.active,
        sa_type=String(16),  # type: ignore
    )
    note: str | None = Field(default=None, max_length=256)
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class MedicationStatementPublic(SQLModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    medication: str
    dose: str
    route: str
    frequency: str
    status: MedicationStatus
    note: str | None
    started_at: datetime | None
