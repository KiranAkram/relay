"""Append-only audit trail.

Every meaningful action (upload, edit, confirm, acknowledge, flag fired, ...)
inserts one row. A database trigger (see migration c3e5a7b9d1f3) rejects
UPDATE and DELETE, so rows cannot be altered even by the app's own DB user.

Deliberately no foreign keys and no soft-delete: the log must outlive whatever
it refers to, so ids are stored as plain UUIDs.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.common import get_datetime_utc


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    occurred_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )

    # Who / what context. NULL actor = system (pipeline) action.
    actor_id: uuid.UUID | None = Field(default=None, index=True)
    handover_id: uuid.UUID | None = Field(default=None, index=True)
    patient_id: uuid.UUID | None = Field(default=None, index=True)

    # e.g. action="task.acknowledged", entity_type="task", entity_id=<task id>
    action: str = Field(max_length=64, index=True)
    entity_type: str = Field(max_length=64)
    entity_id: uuid.UUID | None = None
    # Free-form context, e.g. {"before": {...}, "after": {...}}
    details: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    request_id: str | None = Field(default=None, max_length=64)
