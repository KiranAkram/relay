"""All table models must be importable from here so that Alembic
(`from app.models import SQLModel`) sees every table in `SQLModel.metadata`."""

from sqlmodel import SQLModel

from app.models.allergy_intolerance import (
    AllergyIntolerance,
    AllergyIntolerancePublic,
    AllergySeverity,
)
from app.models.audit_log import AuditLog
from app.models.common import (
    Message,
    SoftDeleteMixin,
    TimestampMixin,
    get_datetime_utc,
)
from app.models.condition import Condition, ConditionPublic, ConditionStatus
from app.models.dashboard import (
    DashboardHandoverStatus,
    DashboardPatientPublic,
    DashboardPublic,
)
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
from app.models.medication_statement import (
    MedicationStatement,
    MedicationStatementPublic,
    MedicationStatus,
)
from app.models.observation import (
    Observation,
    ObservationCategory,
    ObservationInterpretation,
    ObservationPublic,
)
from app.models.patient import (
    CodeStatus,
    Patient,
    PatientBase,
    PatientCreate,
    PatientPublic,
    PatientsPublic,
    PatientUpdate,
    Sex,
)
from app.models.patient_location import PatientLocation, PatientLocationPublic
from app.models.patient_record import PatientRecordCardPublic, PatientRecordPublic
from app.models.task import (
    DueKind,
    Task,
    TaskCancel,
    TaskPriority,
    TaskPublic,
    TaskStatus,
)
from app.models.usage_counter import QuotaPublic, UsageCounter
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
    "CodeStatus",
    "Patient",
    "PatientBase",
    "PatientCreate",
    "PatientPublic",
    "PatientsPublic",
    "PatientUpdate",
    "PatientRecordCardPublic",
    "PatientRecordPublic",
    "Sex",
    # patient clinical record (FHIR-shaped)
    "AllergyIntolerance",
    "AllergyIntolerancePublic",
    "AllergySeverity",
    "Condition",
    "ConditionPublic",
    "ConditionStatus",
    "MedicationStatement",
    "MedicationStatementPublic",
    "MedicationStatus",
    "Observation",
    "ObservationCategory",
    "ObservationInterpretation",
    "ObservationPublic",
    "PatientLocation",
    "PatientLocationPublic",
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
    "TaskCancel",
    "TaskPublic",
    "TaskStatus",
    "TaskPriority",
    "DueKind",
    "Flag",
    "FlagCategory",
    "FlagPublic",
    "FlagStatus",
    "AuditLog",
    # demo limits
    "QuotaPublic",
    "UsageCounter",
    # dashboard
    "DashboardHandoverStatus",
    "DashboardPatientPublic",
    "DashboardPublic",
]
