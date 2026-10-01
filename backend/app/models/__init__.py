"""All table models must be importable from here so that Alembic
(`from app.models import SQLModel`) sees every table in `SQLModel.metadata`."""

from sqlmodel import SQLModel

from app.models.common import (
    Message,
    SoftDeleteMixin,
    TimestampMixin,
    get_datetime_utc,
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
    "Sex",
]
