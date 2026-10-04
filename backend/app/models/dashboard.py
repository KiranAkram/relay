"""Read model for the incoming doctor's dashboard (no table).

One row per census patient with a confirmed card. Priority is the stated
illness severity, then the nearest due task — no computed risk score.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel

from app.models.flag import FlagPublic
from app.models.handover_patient import IllnessSeverity
from app.models.patient import PatientPublic
from app.models.task import TaskPublic


class DashboardPatientPublic(SQLModel):
    patient: PatientPublic
    # Latest confirmed card for this patient
    handover_id: uuid.UUID
    card_id: uuid.UUID
    confirmed_at: datetime
    illness_severity: IllnessSeverity
    patient_summary: str | None
    situation_awareness: str | None
    contingencies: list[dict[str, Any]]
    pending_results: list[dict[str, Any]]
    # Open (requested/accepted) tasks and active flags across all handovers
    tasks: list[TaskPublic]
    flags: list[FlagPublic]
    next_due_at: datetime | None


class DashboardPublic(SQLModel):
    generated_at: datetime
    patients: list[DashboardPatientPublic]
