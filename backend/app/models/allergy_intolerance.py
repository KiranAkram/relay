"""Allergy or intolerance on a patient's record (≈ FHIR AllergyIntolerance).

Convention: a patient with no rows has no known allergies. There is no
separate "no known allergies" marker in the prototype.
"""

import uuid
from enum import StrEnum

from sqlalchemy import String
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class AllergySeverity(StrEnum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    unknown = "unknown"


class AllergyIntolerance(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    __tablename__ = "allergy_intolerance"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    substance: str = Field(min_length=1, max_length=128)
    reaction: str | None = Field(default=None, max_length=256)
    severity: AllergySeverity = Field(
        default=AllergySeverity.unknown,
        sa_type=String(16),  # type: ignore
    )


class AllergyIntolerancePublic(SQLModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    substance: str
    reaction: str | None
    severity: AllergySeverity
