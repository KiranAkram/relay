"""Census and the permanent patient record.

Any doctor can read the census and a patient's record. Only admins change the
census. Patients are never deleted: discharge sets `active=false`, which takes
them off the dashboard while their record stays readable.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app import audit
from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.models import (
    DocumentReference,
    DocumentReferencePublic,
    Flag,
    FlagPublic,
    Handover,
    HandoverPatient,
    HandoverPatientPublic,
    HandoverStatus,
    Patient,
    PatientCreate,
    PatientPublic,
    PatientRecordCardPublic,
    PatientRecordPublic,
    PatientsPublic,
    PatientUpdate,
    Task,
    TaskPublic,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/", response_model=PatientsPublic)
def read_patients(
    session: SessionDep,
    current_user: CurrentUser,  # noqa: ARG001 — any logged-in doctor
    include_discharged: bool = False,
) -> Any:
    """
    The census, ordered by bed.
    """
    statement = select(Patient).where(col(Patient.deleted_at).is_(None))
    if not include_discharged:
        statement = statement.where(col(Patient.active).is_(True))
    patients = sorted(session.exec(statement).all(), key=_bed_key)
    return PatientsPublic(
        data=[PatientPublic.model_validate(p) for p in patients], count=len(patients)
    )


@router.get("/{id}", response_model=PatientPublic)
def read_patient(
    session: SessionDep,
    current_user: CurrentUser,  # noqa: ARG001
    id: uuid.UUID,
) -> Any:
    """
    Get a patient by ID.
    """
    return _get_patient(session, id)


@router.post("/", response_model=PatientPublic)
def create_patient(
    *, session: SessionDep, current_user: AdminUser, patient_in: PatientCreate
) -> Any:
    """
    Admit a patient to the census (admin).
    """
    _require_free_mrn(session, patient_in.mrn)
    patient = Patient.model_validate(patient_in)
    session.add(patient)
    audit.record(
        session,
        "patient.created",
        "patient",
        actor_id=current_user.id,
        patient_id=patient.id,
        entity_id=patient.id,
        details={"after": patient_in.model_dump(mode="json")},
    )
    _commit_or_409(session)
    session.refresh(patient)
    return patient


@router.patch("/{id}", response_model=PatientPublic)
def update_patient(
    *,
    session: SessionDep,
    current_user: AdminUser,
    id: uuid.UUID,
    patient_in: PatientUpdate,
) -> Any:
    """
    Update census details (admin). Discharge is a separate action.
    """
    patient = _get_patient(session, id)
    update = patient_in.model_dump(exclude_unset=True)
    if "active" in update:
        raise HTTPException(
            status_code=400, detail="Use /patients/{id}/discharge to change active"
        )
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if "mrn" in update and update["mrn"] != patient.mrn:
        _require_free_mrn(session, update["mrn"])

    before = patient.model_dump(mode="json", include=set(update))
    patient.sqlmodel_update(update)
    session.add(patient)
    audit.record(
        session,
        "patient.updated",
        "patient",
        actor_id=current_user.id,
        patient_id=patient.id,
        entity_id=patient.id,
        details={
            "before": before,
            "after": patient.model_dump(mode="json", include=set(update)),
        },
    )
    _commit_or_409(session)
    session.refresh(patient)
    return patient


@router.post("/{id}/discharge", response_model=PatientPublic)
def discharge_patient(
    session: SessionDep, current_user: AdminUser, id: uuid.UUID
) -> Any:
    """
    Take a patient off the census (admin). The record is kept.
    """
    patient = _get_patient(session, id)
    if not patient.active:
        raise HTTPException(status_code=409, detail="Patient is already discharged")
    patient.active = False
    session.add(patient)
    audit.record(
        session,
        "patient.discharged",
        "patient",
        actor_id=current_user.id,
        patient_id=patient.id,
        entity_id=patient.id,
        details={"bed": patient.bed, "at": datetime.now(UTC).isoformat()},
    )
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/{id}/record", response_model=PatientRecordPublic)
def read_patient_record(
    session: SessionDep,
    current_user: CurrentUser,  # noqa: ARG001
    id: uuid.UUID,
) -> Any:
    """
    Everything confirmed into this patient's record, newest first.
    """
    patient = _get_patient(session, id)
    cards = session.exec(
        select(HandoverPatient, Handover)
        .join(Handover, col(HandoverPatient.handover_id) == col(Handover.id))
        .where(
            HandoverPatient.patient_id == patient.id,
            col(HandoverPatient.deleted_at).is_(None),
            Handover.status == HandoverStatus.confirmed,
            col(Handover.deleted_at).is_(None),
        )
        .order_by(col(Handover.confirmed_at).desc())
    ).all()
    tasks = session.exec(
        select(Task)
        .where(Task.patient_id == patient.id, col(Task.deleted_at).is_(None))
        .order_by(col(Task.created_at).desc())
    ).all()
    flags = session.exec(
        select(Flag)
        .where(Flag.patient_id == patient.id, col(Flag.deleted_at).is_(None))
        .order_by(col(Flag.fire_at).desc())
    ).all()
    documents = session.exec(
        select(DocumentReference)
        .where(
            DocumentReference.patient_id == patient.id,
            col(DocumentReference.deleted_at).is_(None),
        )
        .order_by(col(DocumentReference.authored_at).desc())
    ).all()
    return PatientRecordPublic(
        patient=PatientPublic.model_validate(patient),
        cards=[
            PatientRecordCardPublic(
                card=HandoverPatientPublic.model_validate(card),
                handover_id=handover.id,
                author_id=handover.author_id,
                recorded_at=handover.recorded_at,
                confirmed_at=handover.confirmed_at,
                shift_label=handover.shift_label,
            )
            for card, handover in cards
            if handover.confirmed_at is not None  # always true for `confirmed`
        ],
        tasks=[TaskPublic.model_validate(t) for t in tasks],
        flags=[FlagPublic.model_validate(f) for f in flags],
        documents=[DocumentReferencePublic.model_validate(d) for d in documents],
    )


# --- helpers ---------------------------------------------------------------


def _get_patient(session: SessionDep, id: uuid.UUID) -> Patient:
    patient = session.get(Patient, id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _require_free_mrn(session: SessionDep, mrn: str) -> None:
    if session.exec(select(Patient).where(Patient.mrn == mrn)).first() is not None:
        raise HTTPException(status_code=409, detail=f"MRN {mrn} is already in use")


def _commit_or_409(session: SessionDep) -> None:
    """The MRN pre-check can lose a race; the unique index is the real guard."""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="MRN is already in use") from None


def _bed_key(patient: Patient) -> tuple[Any, ...]:
    """Natural order: CCU-7 before CCU-10; patients without a bed last."""
    if not patient.bed:
        return (1, [], patient.family_name)
    parts = [
        int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", patient.bed)
    ]
    return (0, [(isinstance(p, str), p) for p in parts], patient.family_name)
