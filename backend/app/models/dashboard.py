"""Read model for the incoming doctor's dashboard (no table).

One row per active census patient. Patients with a confirmed card carry it;
patients nobody handed over are listed too, marked `no_handover`, because a
patient missing from the list is the failure a handover tool exists to
prevent. Priority is the stated illness severity, then the nearest due task —
no computed risk score.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlmodel import SQLModel

from app.models.flag import FlagPublic
from app.models.handover_patient import IllnessSeverity
from app.models.patient import PatientPublic
from app.models.task import TaskPublic


class DashboardHandoverStatus(StrEnum):
    handed_over = "handed_over"
    no_handover = "no_handover"


class DashboardPatientPublic(SQLModel):
    patient: PatientPublic
    handover_status: DashboardHandoverStatus
    # Latest confirmed card for this patient; None when `no_handover`
    # Every field is always present so the generated client types are exact.
    handover_id: uuid.UUID | None
    card_id: uuid.UUID | None
    confirmed_at: datetime | None
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
