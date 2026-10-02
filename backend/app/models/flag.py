"""Alert attached to a patient (≈ FHIR Flag).

Created by the confirm transaction. There is no scheduler: `fire_at` is
precomputed (e.g. task.due_at minus the alert lead time, or "now" for an
unstable patient) and a flag counts as fired when `now >= fire_at` and it has
not been acknowledged. `fired_at` is stamped the first time a client sees it,
so there is a permanent record of when the alert went off.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class FlagCategory(StrEnum):
    task_due_soon = "task_due_soon"
    task_overdue = "task_overdue"
    unstable_patient = "unstable_patient"


# FHIR Flag.status
class FlagStatus(StrEnum):
    active = "active"
    inactive = "inactive"


class Flag(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    handover_id: uuid.UUID = Field(
        foreign_key="handover.id", nullable=False, index=True, ondelete="CASCADE"
    )
    # NULL for patient-level flags (unstable_patient)
    task_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="task.id",
        nullable=True,
        index=True,
        ondelete="CASCADE",
    )

    category: FlagCategory = Field(sa_type=String(32))  # type: ignore
    status: FlagStatus = Field(
        default=FlagStatus.active,
        sa_type=String(16),  # type: ignore
        index=True,
    )

    fire_at: datetime = Field(sa_type=DateTime(timezone=True), index=True)  # type: ignore
    fired_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    acknowledged_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="RESTRICT"
    )
    acknowledged_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
