"""Action item from a confirmed handover (≈ FHIR Task).

Rows are created only by the confirm transaction, one per action item the
doctor confirmed. `due_at` is absolute (UTC), already resolved from whatever
was spoken ("by 8:30", "in an hour"). Status follows FHIR Task.status:
requested → accepted (incoming doctor acknowledged) → completed | cancelled.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, Text
from sqlmodel import Field, SQLModel

from app.models.common import SoftDeleteMixin, TimestampMixin


class TaskStatus(StrEnum):
    requested = "requested"
    accepted = "accepted"  # acknowledged by the incoming doctor (closed loop)
    completed = "completed"
    cancelled = "cancelled"


# FHIR Task.priority subset
class TaskPriority(StrEnum):
    routine = "routine"
    urgent = "urgent"
    stat = "stat"


# How the due time was spoken; the absolute value is in `due_at`.
class DueKind(StrEnum):
    clock = "clock"  # "by 8:30"
    relative = "relative"  # "in an hour"
    unspecified = "unspecified"  # no time given


class Task(TimestampMixin, SoftDeleteMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    handover_patient_id: uuid.UUID = Field(
        foreign_key="handover_patient.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    # Denormalised from handover_patient so the dashboard can query without joins.
    handover_id: uuid.UUID = Field(
        foreign_key="handover.id", nullable=False, index=True, ondelete="CASCADE"
    )
    patient_id: uuid.UUID = Field(
        foreign_key="patient.id", nullable=False, index=True, ondelete="RESTRICT"
    )

    description: str = Field(sa_type=Text)
    due_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )
    due_kind: DueKind = Field(
        default=DueKind.unspecified,
        sa_type=String(16),  # type: ignore
    )
    due_phrase: str | None = Field(default=None, max_length=128)  # "by 8:30"
    priority: TaskPriority = Field(
        default=TaskPriority.routine,
        sa_type=String(16),  # type: ignore
    )
    status: TaskStatus = Field(
        default=TaskStatus.requested,
        sa_type=String(16),  # type: ignore
        index=True,
    )
    verbatim: str | None = Field(default=None, sa_type=Text)

    acknowledged_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="RESTRICT"
    )
    acknowledged_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    completed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="RESTRICT"
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # Set only when status is `cancelled`; shown on the patient record.
    cancel_reason: str | None = Field(default=None, sa_type=Text)


# Properties to return via API
class TaskPublic(SQLModel):
    id: uuid.UUID
    handover_patient_id: uuid.UUID
    handover_id: uuid.UUID
    patient_id: uuid.UUID
    description: str
    due_at: datetime | None
    due_kind: DueKind
    due_phrase: str | None
    priority: TaskPriority
    status: TaskStatus
    verbatim: str | None
    acknowledged_by_id: uuid.UUID | None
    acknowledged_at: datetime | None
    completed_by_id: uuid.UUID | None
    completed_at: datetime | None
    cancel_reason: str | None
    created_at: datetime


class TaskCancel(SQLModel):
    reason: str = Field(min_length=3, max_length=500)
