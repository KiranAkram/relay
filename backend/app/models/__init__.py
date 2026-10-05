"""All table models must be importable from here so that Alembic
(`from app.models import SQLModel`) sees every table in `SQLModel.metadata`."""

from sqlmodel import SQLModel

from app.models.audit_log import AuditLog
from app.models.common import (
    Message,
    SoftDeleteMixin,
    TimestampMixin,
    get_datetime_utc,
)
from app.models.dashboard import DashboardPatientPublic, DashboardPublic
from app.models.document_reference import (
    DocumentReference,
    DocumentReferencePublic,
    DocumentType,
)
from app.models.flag import Flag, FlagCategory, FlagPublic, FlagStatus
from app.models.handover import (
    Handover,
    HandoverDetailPublic,
    HandoverPublic,
    HandoversPublic,
    HandoverStatus,
)
from app.models.handover_patient import (
    ActionItemDraft,
    HandoverPatient,
    HandoverPatientPublic,
    HandoverPatientUpdate,
    IllnessSeverity,
    MatchCandidatePublic,
    MatchStatus,
)
from app.models.item import (
    Item,
    ItemBase,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
)
from app.models.patient import (
    Patient,
    PatientBase,
    PatientCreate,
    PatientPublic,
    PatientsPublic,
    PatientUpdate,
    Sex,
)
from app.models.patient_record import PatientRecordCardPublic, PatientRecordPublic
from app.models.task import DueKind, Task, TaskPriority, TaskPublic, TaskStatus
from app.models.user import (
    NewPassword,
    Token,
    TokenPayload,
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UserRole,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    "SQLModel",
    # common
    "Message",
    "SoftDeleteMixin",
    "TimestampMixin",
    "get_datetime_utc",
    # user
    "NewPassword",
    "Token",
    "TokenPayload",
    "UpdatePassword",
    "User",
    "UserBase",
    "UserCreate",
    "UserPublic",
    "UserRegister",
    "UserRole",
    "UsersPublic",
    "UserUpdate",
    "UserUpdateMe",
    # item
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
    # patient
    "Patient",
    "PatientBase",
    "PatientCreate",
    "PatientPublic",
    "PatientsPublic",
    "PatientUpdate",
    "PatientRecordCardPublic",
    "PatientRecordPublic",
    "Sex",
    # handover
    "Handover",
    "HandoverDetailPublic",
    "HandoverPublic",
    "HandoversPublic",
    "HandoverStatus",
    "ActionItemDraft",
    "HandoverPatient",
    "HandoverPatientPublic",
    "HandoverPatientUpdate",
    "IllnessSeverity",
    "MatchCandidatePublic",
    "MatchStatus",
    "DocumentReference",
    "DocumentReferencePublic",
    "DocumentType",
    # task / flag / audit
    "Task",
    "TaskPublic",
    "TaskStatus",
    "TaskPriority",
    "DueKind",
    "Flag",
    "FlagCategory",
    "FlagPublic",
    "FlagStatus",
    "AuditLog",
    # dashboard
    "DashboardPatientPublic",
    "DashboardPublic",
]
