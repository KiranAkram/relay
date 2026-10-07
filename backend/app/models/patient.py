"""Patient census.

Shaped after FHIR R4 `Patient` (identifier=mrn, name, birthDate, gender).
`bed`/`unit`/`admitted_at` belong to `Encounter.location` / `Encounter.period`
in FHIR; they live here for now because the prototype has no Encounter table.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, text
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


# FHIR AdministrativeGender
class Sex(StrEnum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


# Resuscitation status as the ward records it. Stored on the patient for the
# prototype; FHIR models it as a Consent/Flag resource.
class CodeStatus(StrEnum):
    full_code = "full_code"
    dnr = "dnr"  # do not attempt resuscitation
    dnr_dni = "dnr_dni"  # ... and do not intubate
    comfort_care = "comfort_care"


# Shared properties
class PatientBase(SQLModel):
    mrn: str = Field(unique=True, index=True, min_length=1, max_length=32)
    family_name: str = Field(min_length=1, max_length=128)
    given_name: str = Field(min_length=1, max_length=128)
    birth_date: date | None = None
    sex: Sex = Field(default=Sex.unknown, sa_type=String(16))  # type: ignore
    bed: str | None = Field(default=None, index=True, max_length=32)
    unit: str | None = Field(default=None, max_length=64)
    admitting_diagnosis: str | None = Field(default=None, max_length=512)
    attending_name: str | None = Field(default=None, max_length=128)
    admitted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    code_status: CodeStatus = Field(
        default=CodeStatus.full_code,
        sa_type=String(16),  # type: ignore
    )
    # True for every fabricated record (seed). No real PHI is ever marked False
    # by accident: only an admin creating a real patient leaves it False.
    synthetic: bool = False
    # False once discharged; the census is `active AND deleted_at IS NULL`.
    active: bool = True


# Properties to receive on patient creation
class PatientCreate(PatientBase):
    pass


# Properties to receive on patient update, all are optional
class PatientUpdate(SQLModel):
    mrn: str | None = Field(default=None, min_length=1, max_length=32)
    family_name: str | None = Field(default=None, min_length=1, max_length=128)
    given_name: str | None = Field(default=None, min_length=1, max_length=128)
    birth_date: date | None = None
    sex: Sex | None = None
    bed: str | None = Field(default=None, max_length=32)
    unit: str | None = Field(default=None, max_length=64)
    admitting_diagnosis: str | None = Field(default=None, max_length=512)
    attending_name: str | None = Field(default=None, max_length=128)
    admitted_at: datetime | None = None
    code_status: CodeStatus | None = None
    active: bool | None = None


# Database model, database table inferred from class name
class Patient(PatientBase, TimestampMixin, SoftDeleteMixin, table=True):
    # One patient per bed: the database refuses a second active, undeleted
    # patient in an occupied bed. Discharged or deleted rows free the bed.
    __table_args__ = (
        Index(
            "ux_patient_bed_active",
            "bed",
            unique=True,
            postgresql_where=text("active AND deleted_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Properties to return via API, id is always required
class PatientPublic(PatientBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PatientsPublic(SQLModel):
    data: list[PatientPublic]
    count: int
