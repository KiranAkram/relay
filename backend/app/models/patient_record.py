"""Read model for one patient's permanent record (no table).

Everything that reached the patient through confirmed handovers: the cards as
confirmed, every task and flag, and the audio references. Drafts never appear.
"""

import uuid
from datetime import datetime

from sqlmodel import SQLModel

from app.models.document_reference import DocumentReferencePublic
from app.models.flag import FlagPublic
from app.models.handover_patient import HandoverPatientPublic
from app.models.patient import PatientPublic
from app.models.task import TaskPublic


class PatientRecordCardPublic(SQLModel):
    card: HandoverPatientPublic
    handover_id: uuid.UUID
    author_id: uuid.UUID
    recorded_at: datetime
    confirmed_at: datetime
    shift_label: str | None


class PatientRecordPublic(SQLModel):
    patient: PatientPublic
    # Newest confirmed handover first
    cards: list[PatientRecordCardPublic]
    tasks: list[TaskPublic]
    flags: list[FlagPublic]
    documents: list[DocumentReferencePublic]
